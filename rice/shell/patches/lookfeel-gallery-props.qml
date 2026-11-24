    // fastfetch logo gallery (ff-logo): pictures or ASCII art to pick from
    property var gal: ({ logo: "", mode: "image", items: [] })
    function galRun(args) {
        const g = Object.assign({}, gal)
        if (args[0] === "mode") g.mode = args[1]
        else if (args[0] === "set") g.logo = args[1]
        else if (args[0] === "layout") g.layout = args[1]
        gal = g
        galSet.command = ["bash", "-c", "\"$HOME/.local/share/dss/bin/ff-logo\" \"$@\" >/dev/null 2>&1", "_"].concat(args)
        galSet.running = true
    }
    Process {
        id: galState
        command: ["bash", "-c", "\"$HOME/.local/share/dss/bin/ff-logo\" list"]
        running: true
        stdout: StdioCollector { onStreamFinished: { try { page.gal = JSON.parse(text) } catch (e) { } } }
    }
    Process { id: galSet; onExited: galState.running = true }
