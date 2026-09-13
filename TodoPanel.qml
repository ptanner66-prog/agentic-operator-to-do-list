import QtQuick
import QtQuick.Controls as Controls
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

Panel {
  id: root
  moduleName: "portertanner.operator-todos"
  manageIpc: false
  property var anchorItem: null
  property var hostWidget: null
  readonly property var ownerItem: hostWidget || root
  readonly property string backend: decodeURIComponent(Qt.resolvedUrl("operator_todos.py").toString().replace(/^file:\/\//, ""))
  readonly property color fg: root.bar ? root.bar.barForeground : Color.foreground
  readonly property color muted: Qt.alpha(root.fg, 0.55)
  property var rows: []
  property int attention: 0
  property string term: "short"
  property bool history: false
  property string expanded: ""
  property var drafts: ({})
  property string error: ""
  property bool connected: false
  property bool pending: false
  property string submittedTitle: ""
  property string requestedCommand: ""
  property bool agentsView: false
  property var agentStatus: []
  property var liveAgents: []
  readonly property bool attentionIndicatorVisible: root.attention > 0 && !root.opened
  property string setupMessage: ""
  property double now: Date.now() / 1000
  readonly property bool busy: root.pending || actionProcess.running
  function open() {
    if (!root.expanded && !root.history) {
      var pending = rows.filter(function(x) { return x.term === root.term && x.status === "open" && x.important })
      if (pending.length) root.expanded = pending[0].id
    }
    root.controller.show()
  }
  readonly property var shown: rows.filter(function(x) {
    if (x.term !== root.term) return false
    var finished = x.status === "done" || x.status === "dismissed"
    return root.history ? finished : !finished
  })
  function act(id, action, extra) {
    if (root.busy) return
    var payload = extra || {}
    payload.id = id
    payload.action = action
    root.run("act", payload)
  }
  function run(command, data) {
    if (root.busy) return
    root.pending = true
    root.requestedCommand = command
    root.error = ""
    actionProcess.command = ["python3", root.backend, command, JSON.stringify(data)]
    actionProcess.running = true
  }
  function add() {
    if (root.busy) return
    if (!addInput.text.trim()) { addInput.forceActiveFocus(); return }
    root.submittedTitle = addInput.text.trim()
    root.run("post", {title: root.submittedTitle, term: root.term, kind: "task"})
    root.history = false
    list.contentY = 0
  }
  function agentConnected(source) {
    return root.connected && root.liveAgents.some(function(x) { return x.source === source })
  }
  function sourceLabel(item) {
    return item.source === "manual" ? "" : item.source.charAt(0).toUpperCase() + item.source.slice(1) + (item.project ? " · " + item.project : "")
  }
  function deliveryLabel(item) {
    if (item.status === "dismissed") return item.delivery === "acknowledged" ? "Dismissed · agent acknowledged" : "Dismissed"
    if (item.delivery === "acknowledged") return "Agent acknowledged"
    if (item.unacknowledged) return (item.delivery === "sent" ? "Sent to conversation" : "Handed to waiting agent") + " · no acknowledgement yet, retry or check the chat"
    if (item.delivery === "received") return "Handed to waiting agent"
    if (item.delivery === "sent") return "Sent to conversation"
    if (item.delivery === "failed") return "Reply saved · delivery failed, see details"
    if (item.delivery === "saved") return item.source === "codex" && !item.session_id ? "Reply saved · no conversation ID, the agent must read it" : "Reply saved · waiting for agent"
    if (item.snoozed_until > root.now) return "Snoozed for an hour"
    return ""
  }
  Process {
    id: watcher
    command: ["python3", root.backend, "watch"]
    running: true
    stdout: SplitParser {
      onRead: function(line) {
        try {
          var state = JSON.parse(line)
          if (!Array.isArray(state.items)) throw new Error(state.error || "Invalid state")
          root.rows = state.items
          root.attention = state.attention
          root.liveAgents = state.live_agents || []
          root.now = state.now
          root.connected = true
        } catch (e) { root.error = "Could not read to-dos: " + e.message }
      }
    }
    onExited: { root.connected = false; reconnect.restart() }
  }
  Timer { id: reconnect; interval: 5000; onTriggered: watcher.running = true }
  Process {
    id: actionProcess
    stdout: StdioCollector { id: actionOutput }
    stderr: StdioCollector { id: actionError }
    onExited: function(exitCode, exitStatus) {
      root.pending = false
      try {
        var result = JSON.parse(actionOutput.text)
        if (!result.ok) root.error = result.error || "Action failed"
        else if (root.requestedCommand === "post") {
          if (addInput.text.trim() === root.submittedTitle) addInput.text = ""
          addInput.forceActiveFocus()
        } else if (root.requestedCommand === "setup-status" || root.requestedCommand === "connect" || root.requestedCommand === "disconnect") {
          root.agentStatus = result.result.agents
          root.setupMessage = result.result.message || ""
        }
      } catch (e) {
        root.error = actionError.text.trim() || "Could not save that change. Your text is still here; try again."
      }
    }
    onRunningChanged: if (!running && root.pending) pendingReset.restart()
  }
  Timer { id: pendingReset; interval: 500; onTriggered: { if (root.pending && !actionProcess.running) { root.pending = false; root.error = "Could not start the to-do service. Your text is still here." } } }
  KeyboardPanel {
    id: popup
    anchorItem: root.anchorItem
    owner: root.ownerItem
    bar: root.bar
    open: root.opened
    centerOnBar: false
    focusTarget: root.agentsView ? content : addInput
    contentWidth: popup.fittedContentWidth(Style.space(480))
    contentHeight: popup.cappedContentHeight(Style.space(600))
    Column {
      id: content
      width: parent.width
      height: parent.height
      spacing: Style.space(10)
      focus: true
      Keys.onEscapePressed: root.close()
      Keys.onPressed: function(event) {
        if (event.key === Qt.Key_PageDown || event.key === Qt.Key_PageUp) {
          var direction = event.key === Qt.Key_PageDown ? 1 : -1
          list.contentY = Math.max(0, Math.min(Math.max(0, list.contentHeight - list.height), list.contentY + direction * list.height * 0.9))
          event.accepted = true
        }
      }
      Row {
        width: parent.width
        Text {
          width: parent.width - agentsButton.width - doneButton.width - closeButton.width
          anchors.verticalCenter: parent.verticalCenter
          text: root.agentsView ? "Agents" : "To-dos"
          textFormat: Text.PlainText
          color: root.fg
          font.family: Style.font.family
          font.pixelSize: Style.font.body
          font.bold: true
        }
        Button { id: agentsButton; text: root.agentsView ? "Back" : "Agents"; fontSize: Style.font.bodySmall; foreground: root.muted; focusable: true; onClicked: { root.agentsView = !root.agentsView; if (root.agentsView) root.run("setup-status", {}) } }
        Button { id: doneButton; visible: !root.agentsView; width: visible ? implicitWidth : 0; text: root.history ? "Back" : "History"; fontSize: Style.font.bodySmall; foreground: root.muted; focusable: true; onClicked: { root.history = !root.history; root.expanded = ""; list.contentY = 0 } }
        PanelActionButton { id: closeButton; iconText: "×"; tooltipText: "Close list"; foreground: root.muted; focusable: true; onClicked: root.close() }
      }
      Row {
        visible: !root.agentsView
        width: parent.width
        spacing: Style.space(6)
        Repeater {
          id: termTabs
          model: ["short", "long"]
          Button {
            required property string modelData
            width: (content.width - Style.space(6)) / 2
            text: modelData === "short" ? "Short term" : "Long term"
            selected: root.term === modelData
            foreground: root.fg
            focusable: true
            onClicked: { root.term = modelData; root.expanded = ""; list.contentY = 0 }
          }
        }
      }
      Row {
        visible: !root.agentsView
        width: parent.width
        spacing: Style.space(6)
        TextField {
          id: addInput
          width: parent.width - addButton.width - parent.spacing
          placeholderText: "Add a to-do…"
          foreground: root.fg
          maximumLength: 200
          readOnly: root.busy
          onAccepted: root.add()
          Accessible.name: "New to-do"
        }
        Button { id: addButton; text: root.busy && root.requestedCommand === "post" ? "Saving…" : "+ Add"; height: addInput.height; fontSize: Style.font.body; foreground: root.fg; focusable: true; bordered: true; enabled: !root.busy; tooltipText: addInput.text.trim() ? "Save to this list" : "Write a new to-do"; onClicked: root.add(); Accessible.name: "Add to-do" }
      }
      Text {
        visible: root.error !== "" || !root.connected
        width: parent.width
        text: root.error || "Connecting…"
        textFormat: Text.PlainText
        wrapMode: Text.Wrap
        color: root.error ? Color.urgent : root.muted
        font.family: Style.font.family
        font.pixelSize: Style.font.bodySmall
      }
      Flickable {
        id: list
        visible: !root.agentsView
        width: parent.width
        height: Math.max(0, content.height - y)
        contentWidth: width
        contentHeight: entries.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.VerticalFlick
        Controls.ScrollBar.vertical: Controls.ScrollBar {
          width: Style.space(5)
          policy: Controls.ScrollBar.AsNeeded
          visible: list.contentHeight > list.height
          minimumSize: 0.08
          contentItem: Rectangle {
            implicitWidth: Style.space(5)
            radius: width / 2
            color: Qt.alpha(root.fg, parent.pressed || parent.hovered ? 0.5 : 0.25)
          }
          background: Item {}
        }
        Column {
          id: entries
          width: list.width - Style.space(12)
          spacing: Style.space(2)
          Item {
            visible: root.shown.length === 0
            width: parent.width
            height: visible ? Style.space(78) : 0
            Text {
              anchors.centerIn: parent
              text: root.history ? "Nothing here yet" : "Nothing waiting here"
              textFormat: Text.PlainText
              color: root.muted
              font.family: Style.font.family
              font.pixelSize: Style.font.body
            }
          }
          Repeater {
            model: root.shown
            Column {
              id: entry
              required property var modelData
              width: entries.width
              spacing: Style.space(6)
              readonly property bool isExpanded: root.expanded === modelData.id
              readonly property bool isOpen: modelData.status === "open"
              readonly property bool isAgent: modelData.source !== "manual"
              Item {
                width: parent.width
                height: titleColumn.implicitHeight + Style.space(16)
                PanelActionButton {
                  id: check
                  anchors.left: parent.left
                  anchors.verticalCenter: parent.verticalCenter
                  iconText: entry.isOpen ? "□" : "✓"
                  foreground: root.muted
                  tooltipText: modelData.kind === "task" ? "Mark done" : "Show decision"
                  enabled: !root.busy && entry.isOpen
                  focusable: true
                  onClicked: {
                    if (modelData.kind === "task") root.act(modelData.id, "done")
                    else root.expanded = entry.isExpanded ? "" : modelData.id
                  }
                }
                Column {
                  id: titleColumn
                  anchors.left: check.right
                  anchors.leftMargin: Style.space(5)
                  anchors.right: root.history ? restoreButton.left : dismiss.left
                  anchors.rightMargin: Style.space(4)
                  anchors.verticalCenter: parent.verticalCenter
                  spacing: Style.space(3)
                  Text {
                    width: parent.width
                    text: modelData.title
                    textFormat: Text.PlainText
                    wrapMode: Text.Wrap
                    color: root.fg
                    font.family: Style.font.family
                    font.pixelSize: Style.font.body
                    font.strikeout: modelData.status === "done"
                  }
                  Text {
                    visible: text !== ""
                    width: parent.width
                    text: root.sourceLabel(modelData)
                    textFormat: Text.PlainText
                    elide: Text.ElideRight
                    color: root.muted
                    font.family: Style.font.family
                    font.pixelSize: Style.font.bodySmall
                  }
                  Text {
                    visible: text !== ""
                    width: parent.width
                    text: root.deliveryLabel(modelData)
                    textFormat: Text.PlainText
                    wrapMode: Text.Wrap
                    color: modelData.delivery === "failed" || modelData.unacknowledged ? Color.urgent : root.muted
                    font.family: Style.font.family
                    font.pixelSize: Style.font.bodySmall
                  }
                }
                MouseArea { anchors.fill: titleColumn; cursorShape: Qt.PointingHandCursor; onClicked: root.expanded = entry.isExpanded ? "" : modelData.id }
                PanelActionButton {
                  id: restoreButton
                  visible: root.history
                  anchors.right: dismiss.left
                  anchors.verticalCenter: parent.verticalCenter
                  iconText: "\uf0e2"
                  foreground: root.fg
                  tooltipText: "Move back to " + (modelData.term === "long" ? "long term" : "short term")
                  focusable: true
                  enabled: !root.busy
                  onClicked: root.act(modelData.id, "restore")
                  Accessible.name: "Move back to list"
                }
                PanelActionButton {
                  id: dismiss
                  anchors.right: parent.right
                  anchors.verticalCenter: parent.verticalCenter
                  iconText: entry.isAgent && entry.isOpen ? "×" : "\uf1f8"
                  foreground: root.muted
                  tooltipText: entry.isAgent && entry.isOpen ? "Dismiss request · no approval" : "Delete to-do"
                  focusable: true
                  enabled: !root.busy
                  onClicked: root.act(modelData.id, entry.isAgent && entry.isOpen ? "dismiss" : "delete")
                }
              }
              Column {
                visible: entry.isExpanded
                width: parent.width - Style.space(12)
                x: Style.space(6)
                spacing: Style.space(9)
                Repeater {
                  model: [ {label: "Context", value: entry.modelData.context}, {label: "Recommendation", value: entry.modelData.recommendation}, {label: "What happens", value: entry.modelData.consequence} ]
                  Column {
                    required property var modelData
                    width: parent.width
                    visible: !!modelData.value
                    spacing: Style.space(3)
                    Text { text: modelData.label; textFormat: Text.PlainText; color: root.muted; font.family: Style.font.family; font.pixelSize: Style.font.bodySmall }
                    Text { width: parent.width; text: modelData.value || ""; textFormat: Text.PlainText; wrapMode: Text.Wrap; color: root.fg; font.family: Style.font.family; font.pixelSize: Style.font.body }
                  }
                }
                Text {
                  visible: !!entry.modelData.response
                  width: parent.width
                  text: entry.modelData.response ? "Your response: " + entry.modelData.response.text : ""
                  textFormat: Text.PlainText
                  wrapMode: Text.Wrap
                  color: root.fg
                  font.family: Style.font.family
                  font.pixelSize: Style.font.bodySmall
                }
                Text {
                  visible: !!entry.modelData.delivery_error
                  width: parent.width
                  text: "Delivery problem: " + (entry.modelData.delivery_error || "")
                  textFormat: Text.PlainText
                  wrapMode: Text.Wrap
                  color: Color.urgent
                  font.family: Style.font.family
                  font.pixelSize: Style.font.bodySmall
                }
                Text {
                  visible: entry.isAgent
                  width: parent.width
                  text: entry.modelData.session_id ? "Conversation: " + entry.modelData.session_id : "No conversation ID was supplied; the agent must read the reply itself"
                  textFormat: Text.PlainText
                  wrapMode: Text.Wrap
                  color: root.muted
                  font.family: Style.font.family
                  font.pixelSize: Style.font.bodySmall
                }
                Row {
                  visible: entry.isOpen && entry.modelData.kind === "approval"
                  spacing: Style.space(8)
                  Button { text: "Approve"; foreground: root.fg; bordered: true; focusable: true; enabled: !root.busy; onClicked: root.act(entry.modelData.id, "approve") }
                  Button { text: "Reject"; foreground: root.muted; focusable: true; enabled: !root.busy; onClicked: root.act(entry.modelData.id, "reject") }
                }
                Column {
                  visible: entry.isOpen && entry.modelData.kind === "choice"
                  width: parent.width
                  spacing: Style.space(6)
                  Repeater {
                    model: entry.modelData.options
                    ChoiceButton { required property string modelData; width: parent.width; text: modelData; foreground: root.fg; enabled: !root.busy; onClicked: root.act(entry.modelData.id, "choose", {text: modelData}) }
                  }
                }
                Row {
                  visible: entry.isOpen && entry.isAgent
                  width: parent.width
                  spacing: Style.space(6)
                  TextField {
                    id: replyInput
                    width: parent.width - sendButton.width - parent.spacing
                    placeholderText: "Reply…"
                    text: root.drafts[entry.modelData.id] || ""
                    foreground: root.fg
                    onTextEdited: root.drafts[entry.modelData.id] = text
                    onAccepted: { if (text.trim()) root.act(entry.modelData.id, "reply", {text: text}) }
                    Accessible.name: "Reply to " + entry.modelData.title
                  }
                  Button { id: sendButton; text: "Send"; foreground: root.fg; focusable: true; enabled: replyInput.text.trim() !== "" && !root.busy; onClicked: root.act(entry.modelData.id, "reply", {text: replyInput.text}) }
                }
                Flow {
                  width: parent.width
                  spacing: Style.space(3)
                  Button { visible: root.history; text: "Move back to list"; foreground: root.fg; fontSize: Style.font.bodySmall; focusable: true; enabled: !root.busy; onClicked: root.act(entry.modelData.id, "restore") }
                  Button { visible: !!entry.modelData.chat_url; text: "Open chat ↗"; foreground: root.muted; fontSize: Style.font.bodySmall; focusable: true; onClicked: Qt.openUrlExternally(entry.modelData.chat_url) }
                  Button { text: root.term === "short" ? "Move to long term" : "Move to short term"; foreground: root.muted; fontSize: Style.font.bodySmall; focusable: true; enabled: !root.busy; onClicked: root.act(entry.modelData.id, "move", {term: root.term === "short" ? "long" : "short"}) }
                  Button { visible: entry.modelData.status === "answered" && ["received", "sent", "failed"].indexOf(entry.modelData.delivery) >= 0; text: "Retry delivery"; foreground: root.fg; fontSize: Style.font.bodySmall; focusable: true; enabled: !root.busy; onClicked: root.act(entry.modelData.id, "retry") }
                  Button { visible: entry.isOpen && entry.isAgent; text: "Snooze 1h"; foreground: root.muted; fontSize: Style.font.bodySmall; focusable: true; enabled: !root.busy; onClicked: root.act(entry.modelData.id, "snooze") }
                  Button { text: "Delete"; foreground: root.muted; fontSize: Style.font.bodySmall; focusable: true; enabled: !root.busy; onClicked: root.act(entry.modelData.id, "delete") }
                }
                Item { width: 1; height: Style.space(4) }
              }
              PanelSeparator { width: parent.width; foreground: Qt.alpha(root.fg, 0.4) }
            }
          }
        }
      }
      Flickable {
        visible: root.agentsView
        width: parent.width
        height: Math.max(0, content.height - y)
        contentHeight: setupContent.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        Column {
          id: setupContent
          width: parent.width
          spacing: Style.space(16)
          Text { width: parent.width; text: "Green here means an agent is connected. A red dot on the closed bar icon means a request needs you. Agents post important decisions and to-dos you explicitly request."; textFormat: Text.PlainText; wrapMode: Text.Wrap; color: root.muted; font.family: Style.font.family; font.pixelSize: Style.font.body }
          Repeater {
            model: root.agentStatus
            Column {
              id: agentRow
              required property var modelData
              width: parent.width
              spacing: Style.space(5)
              Row {
                width: parent.width
                spacing: Style.space(7)
                Rectangle { width: Style.space(6); height: width; radius: width / 2; anchors.verticalCenter: parent.verticalCenter; color: root.agentConnected(agentRow.modelData.source) ? "#66bb6a" : root.muted; Accessible.name: root.agentConnected(agentRow.modelData.source) ? "Connected" : "Disconnected" }
                Text { width: parent.width - connectButton.width - disconnectButton.width - Style.space(27); anchors.verticalCenter: parent.verticalCenter; text: modelData.name; textFormat: Text.PlainText; color: root.fg; font.bold: true; font.family: Style.font.family; font.pixelSize: Style.font.body }
                Button { id: connectButton; text: modelData.configured ? "Repair" : "Connect"; foreground: root.fg; bordered: true; focusable: true; enabled: !root.busy; onClicked: root.run("connect", {source: modelData.source}) }
                Button { id: disconnectButton; visible: modelData.configured; width: visible ? implicitWidth : 0; text: "Disconnect"; foreground: root.muted; focusable: true; enabled: !root.busy; onClicked: root.run("disconnect", {sources: [modelData.source]}) }
              }
              Text { text: root.agentConnected(agentRow.modelData.source) ? "Connected" : "Disconnected"; color: root.agentConnected(agentRow.modelData.source) ? "#66bb6a" : root.muted; font.family: Style.font.family; font.pixelSize: Style.font.bodySmall }
              Text { width: parent.width; text: modelData.detail; textFormat: Text.PlainText; wrapMode: Text.Wrap; color: root.muted; font.family: Style.font.family; font.pixelSize: Style.font.bodySmall }
              PanelSeparator { width: parent.width; foreground: Qt.alpha(root.fg, 0.4) }
            }
          }
          Text { width: parent.width; visible: root.setupMessage !== ""; text: root.setupMessage; textFormat: Text.PlainText; wrapMode: Text.Wrap; color: root.fg; font.family: Style.font.family; font.pixelSize: Style.font.bodySmall }
          Text { width: parent.width; text: "Disconnect apps before removing the plugin so their MCP entries do not point at missing files. Hooks installed by this version exit quietly when the plugin is absent."; textFormat: Text.PlainText; wrapMode: Text.Wrap; color: root.muted; font.family: Style.font.family; font.pixelSize: Style.font.bodySmall }
          Row {
            spacing: Style.space(6)
            Button { text: "Refresh connections"; foreground: root.muted; focusable: true; enabled: !root.busy; onClicked: root.run("setup-status", {}) }
            Button { text: "Disconnect all apps"; foreground: root.muted; focusable: true; enabled: !root.busy; onClicked: root.run("disconnect", {}) }
          }
        }
      }
    }
  }
}
