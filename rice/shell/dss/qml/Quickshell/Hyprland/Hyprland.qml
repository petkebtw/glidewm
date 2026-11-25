pragma Singleton
import QtQuick
QtObject {
    property var focusedWorkspace: null
    property var workspaces: ({ values: [] })
    property var activeToplevel: null
}
