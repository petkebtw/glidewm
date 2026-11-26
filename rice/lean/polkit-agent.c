/* polkit-agent: polkit authentication agent for the glidewm session. C rewrite of the Python/GTK agent
 * (2026-11-26): the resident part is GLib and libpolkit-agent only (about 1 MB instead of ~18 MB of Python and
 * GTK). The window is still the themed GTK one: polkit-dialog (Python) runs only while a request is open.
 *
 * polkit-dialog MESSAGE: stdin gets "PROMPT text", "ERROR text", "INFO text", "QUIT"; its stdout answers
 * "PASS password" or "CANCEL". A wrong password shows "Wrong password, try again" and asks again. */
#define POLKIT_AGENT_I_KNOW_API_IS_SUBJECT_TO_CHANGE
#include <polkitagent/polkitagent.h>
#include <string.h>
#include <unistd.h>

typedef struct { PolkitAgentListener parent; } RiceAgent;
typedef struct { PolkitAgentListenerClass parent_class; } RiceAgentClass;
G_DEFINE_TYPE(RiceAgent, rice_agent, POLKIT_AGENT_TYPE_LISTENER)

typedef struct {
	GTask *task;
	PolkitIdentity *ident;
	char *cookie;
	PolkitAgentSession *session;
	GCancellable *cancellable;
	gulong cancel_id;
	GPid pid;
	int to;           /* the dialog's stdin, -1 when closed */
	GIOChannel *from; /* its stdout */
	guint from_watch;
	GString *buf;
	guint retry_id;
	gboolean done, exited;
} Req;

static void start_session(Req *r);

static void req_free(Req *r)
{
	if (r->retry_id) g_source_remove(r->retry_id);
	if (r->session) {
		g_signal_handlers_disconnect_by_data(r->session, r);
		g_object_unref(r->session);
	}
	g_object_unref(r->ident);
	g_free(r->cookie);
	if (r->cancellable) g_object_unref(r->cancellable);
	g_string_free(r->buf, TRUE);
	g_free(r);
}

static void tell(Req *r, const char *cmd, const char *text)
{
	GString *s;
	if (r->to < 0) return;
	s = g_string_new(cmd);
	if (text) {
		const char *p;
		g_string_append_c(s, ' ');
		for (p = text; *p; p++) g_string_append_c(s, *p == '\n' || *p == '\r' ? ' ' : *p);
	}
	g_string_append_c(s, '\n');
	if (write(r->to, s->str, s->len) < 0) { close(r->to); r->to = -1; }
	g_string_free(s, TRUE);
}

/* the answer to polkit; the dialog closes. The Req lives on until the dialog process has exited. */
static void finish(Req *r, gboolean ok)
{
	if (r->done) return;
	r->done = TRUE;
	if (r->cancel_id) { g_signal_handler_disconnect(r->cancellable, r->cancel_id); r->cancel_id = 0; }
	tell(r, "QUIT", NULL);
	if (r->to >= 0) { close(r->to); r->to = -1; }
	if (r->from_watch) { g_source_remove(r->from_watch); r->from_watch = 0; }
	if (r->session && !ok) polkit_agent_session_cancel(r->session);
	if (ok) g_task_return_boolean(r->task, TRUE);
	else   /* polkit answers the D-Bus call only with an error (a plain FALSE left pkexec waiting) */
		g_task_return_new_error(r->task, POLKIT_ERROR, POLKIT_ERROR_CANCELLED, "Authentication dialog was dismissed by the user");
	g_clear_object(&r->task);
	if (r->exited) req_free(r);
}

static void on_request(PolkitAgentSession *s, const char *prompt, gboolean echo, gpointer data)
{
	(void)s; (void)echo;
	tell(data, "PROMPT", prompt);
}

static void on_error(PolkitAgentSession *s, const char *text, gpointer data) { (void)s; tell(data, "ERROR", text); }
static void on_info(PolkitAgentSession *s, const char *text, gpointer data) { (void)s; tell(data, "INFO", text); }

static gboolean retry(gpointer data)
{
	Req *r = data;
	r->retry_id = 0;
	if (!r->done) start_session(r);
	return G_SOURCE_REMOVE;
}

static void on_completed(PolkitAgentSession *s, gboolean gained, gpointer data)
{
	Req *r = data;
	(void)s;
	if (r->done) return;
	if (gained) { finish(r, TRUE); return; }
	if (r->cancellable && g_cancellable_is_cancelled(r->cancellable)) { finish(r, FALSE); return; }
	tell(r, "ERROR", "Wrong password, try again");
	if (!r->retry_id) r->retry_id = g_idle_add(retry, r);   /* a fresh session: not from inside this one's signal */
}

static void start_session(Req *r)
{
	if (r->session) {
		g_signal_handlers_disconnect_by_data(r->session, r);
		g_object_unref(r->session);
	}
	r->session = polkit_agent_session_new(r->ident, r->cookie);
	g_signal_connect(r->session, "request", G_CALLBACK(on_request), r);
	g_signal_connect(r->session, "show-error", G_CALLBACK(on_error), r);
	g_signal_connect(r->session, "show-info", G_CALLBACK(on_info), r);
	g_signal_connect(r->session, "completed", G_CALLBACK(on_completed), r);
	polkit_agent_session_initiate(r->session);
}

static gboolean on_dialog(GIOChannel *ch, GIOCondition cond, gpointer data)
{
	Req *r = data;
	char tmp[1024];
	gssize n;
	char *nl;
	(void)ch; (void)cond;
	n = read(g_io_channel_unix_get_fd(r->from), tmp, sizeof tmp);
	if (n <= 0) {   /* the dialog closed */
		r->from_watch = 0;
		finish(r, FALSE);
		return G_SOURCE_REMOVE;
	}
	g_string_append_len(r->buf, tmp, n);
	while ((nl = memchr(r->buf->str, '\n', r->buf->len))) {
		char *line = g_strndup(r->buf->str, nl - r->buf->str);
		g_string_erase(r->buf, 0, nl - r->buf->str + 1);
		if (g_str_has_prefix(line, "PASS ")) {
			if (r->session) polkit_agent_session_response(r->session, line + 5);
		} else if (!strcmp(line, "CANCEL")) {
			memset(line, 0, strlen(line));
			g_free(line);
			r->from_watch = 0;
			finish(r, FALSE);
			return G_SOURCE_REMOVE;
		}
		memset(line, 0, strlen(line));   /* the password does not stay in freed memory */
		g_free(line);
	}
	return G_SOURCE_CONTINUE;
}

static void on_dialog_exit(GPid pid, int status, gpointer data)
{
	Req *r = data;
	(void)status;
	g_spawn_close_pid(pid);
	r->exited = TRUE;
	if (!r->done) finish(r, FALSE);   /* frees it, now that it has exited */
	else req_free(r);
}

static void on_cancelled(GCancellable *c, gpointer data)
{
	(void)c;
	finish(data, FALSE);
}

static void initiate(PolkitAgentListener *l, const char *action_id, const char *message, const char *icon_name,
                     PolkitDetails *details, const char *cookie, GList *identities, GCancellable *cancellable,
                     GAsyncReadyCallback callback, gpointer user_data)
{
	Req *r = g_new0(Req, 1);
	GList *i;
	GError *err = NULL;
	int out;
	char *argv[] = { "polkit-dialog", (char *)(message ? message : ""), NULL };
	(void)action_id; (void)icon_name; (void)details;

	r->task = g_task_new(l, cancellable, callback, user_data);
	r->buf = g_string_new(NULL);
	r->cookie = g_strdup(cookie);
	r->to = -1;
	for (i = identities; i; i = i->next)
		if (POLKIT_IS_UNIX_USER(i->data)) { r->ident = g_object_ref(i->data); break; }
	if (!r->ident) r->ident = polkit_unix_user_new(getuid());
	if (!g_spawn_async_with_pipes(NULL, argv, NULL, G_SPAWN_SEARCH_PATH | G_SPAWN_DO_NOT_REAP_CHILD, NULL, NULL,
	                              &r->pid, &r->to, &out, NULL, &err)) {
		g_task_return_error(r->task, err);
		g_object_unref(r->task);
		r->task = NULL;
		r->done = r->exited = TRUE;
		req_free(r);
		return;
	}
	r->from = g_io_channel_unix_new(out);
	g_io_channel_set_close_on_unref(r->from, TRUE);
	r->from_watch = g_io_add_watch(r->from, G_IO_IN | G_IO_HUP | G_IO_ERR, on_dialog, r);
	g_io_channel_unref(r->from);
	g_child_watch_add(r->pid, on_dialog_exit, r);
	if (cancellable) {
		r->cancellable = g_object_ref(cancellable);
		r->cancel_id = g_signal_connect(cancellable, "cancelled", G_CALLBACK(on_cancelled), r);
	}
	start_session(r);
}

static gboolean initiate_finish(PolkitAgentListener *l, GAsyncResult *res, GError **error)
{
	(void)l;
	return g_task_propagate_boolean(G_TASK(res), error);
}

static void rice_agent_init(RiceAgent *a) { (void)a; }
static void rice_agent_class_init(RiceAgentClass *k)
{
	PolkitAgentListenerClass *lk = POLKIT_AGENT_LISTENER_CLASS(k);
	lk->initiate_authentication = initiate;
	lk->initiate_authentication_finish = initiate_finish;
}

int main(void)
{
	GError *err = NULL;
	PolkitSubject *subject;
	PolkitAgentListener *agent;
	gpointer handle;

	subject = polkit_unix_session_new_for_process_sync(getpid(), NULL, NULL);
	if (!subject) subject = polkit_unix_process_new_for_owner(getpid(), 0, getuid());
	agent = g_object_new(rice_agent_get_type(), NULL);
	handle = polkit_agent_listener_register(agent, POLKIT_AGENT_REGISTER_FLAGS_NONE, subject, "/org/rice/PolkitAgent",
	                                        NULL, &err);
	if (!handle) {
		g_printerr("polkit-agent: %s\n", err ? err->message : "could not register");
		return 1;
	}
	g_main_loop_run(g_main_loop_new(NULL, FALSE));
	return 0;
}
