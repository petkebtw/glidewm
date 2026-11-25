# glidewm - glide window manager (a dwm fork). The binary is glidewm, so it never replaces a system dwm.
# See LICENSE file for copyright and license details.

include config.mk

SRC = drw.c dwm.c util.c
OBJ = ${SRC:.c=.o}

all: glidewm

.c.o:
	${CC} -c ${CFLAGS} $<

${OBJ}: config.h config.mk

config.h:
	cp config.def.h $@

glidewm: ${OBJ}
	${CC} -o $@ ${OBJ} ${LDFLAGS}

clean:
	rm -f glidewm mwm dwm ${OBJ} glidewm-${VERSION}.tar.gz

dist: clean
	mkdir -p glidewm-${VERSION}
	cp -R LICENSE Makefile README config.def.h config.mk\
		dwm.1 drw.h util.h ${SRC} dwm.png transient.c glidewm-${VERSION}
	tar -cf glidewm-${VERSION}.tar glidewm-${VERSION}
	gzip glidewm-${VERSION}.tar
	rm -rf glidewm-${VERSION}

install: all
	mkdir -p ${DESTDIR}${PREFIX}/bin
	cp -f glidewm ${DESTDIR}${PREFIX}/bin
	chmod 755 ${DESTDIR}${PREFIX}/bin/glidewm
	mkdir -p ${DESTDIR}${MANPREFIX}/man1
	sed "s/VERSION/${VERSION}/g" < dwm.1 > ${DESTDIR}${MANPREFIX}/man1/glidewm.1
	chmod 644 ${DESTDIR}${MANPREFIX}/man1/glidewm.1

uninstall:
	rm -f ${DESTDIR}${PREFIX}/bin/glidewm\
		${DESTDIR}${MANPREFIX}/man1/glidewm.1

.PHONY: all clean dist install uninstall
