# mwm - muxy window manager (a dwm fork). The binary is mwm, so it never replaces a system dwm.
# See LICENSE file for copyright and license details.

include config.mk

SRC = drw.c dwm.c util.c
OBJ = ${SRC:.c=.o}

all: mwm

.c.o:
	${CC} -c ${CFLAGS} $<

${OBJ}: config.h config.mk

config.h:
	cp config.def.h $@

mwm: ${OBJ}
	${CC} -o $@ ${OBJ} ${LDFLAGS}

clean:
	rm -f mwm dwm ${OBJ} mwm-${VERSION}.tar.gz

dist: clean
	mkdir -p mwm-${VERSION}
	cp -R LICENSE Makefile README config.def.h config.mk\
		dwm.1 drw.h util.h ${SRC} dwm.png transient.c mwm-${VERSION}
	tar -cf mwm-${VERSION}.tar mwm-${VERSION}
	gzip mwm-${VERSION}.tar
	rm -rf mwm-${VERSION}

install: all
	mkdir -p ${DESTDIR}${PREFIX}/bin
	cp -f mwm ${DESTDIR}${PREFIX}/bin
	chmod 755 ${DESTDIR}${PREFIX}/bin/mwm
	mkdir -p ${DESTDIR}${MANPREFIX}/man1
	sed "s/VERSION/${VERSION}/g" < dwm.1 > ${DESTDIR}${MANPREFIX}/man1/mwm.1
	chmod 644 ${DESTDIR}${MANPREFIX}/man1/mwm.1

uninstall:
	rm -f ${DESTDIR}${PREFIX}/bin/mwm\
		${DESTDIR}${MANPREFIX}/man1/mwm.1

.PHONY: all clean dist install uninstall
