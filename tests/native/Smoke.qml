import QtQuick
import Quickshell.Io

Item {
  id: test
  property var panel: null
  property int stage: 0
  property int ticks: 0
  property bool finished: false
  property string firstId: ""
  property string agentId: ""
  property double failedAt: 0
  property var checks: []
  function report(ok, message) {
    if (finished) return
    finished = true
    writer.command = ["python3", Qt.resolvedUrl("record.py").toString().replace(/^file:\/\//, ""), JSON.stringify({ok: ok, message: message, checks: checks})]
    writer.running = true
  }
  function check(condition, message) {
    if (!condition) { report(false, message); throw new Error(message) }
    checks.push(message)
  }
  Component.onCompleted: {
    var component = Qt.createComponent("TodoPanel.qml")
    if (component.status !== Component.Ready) { report(false, component.errorString()); return }
    panel = component.createObject(test)
    if (!panel) report(false, "Panel failed to instantiate")
  }
  Process { id: writer }
  Process {
    id: poster
    command: ["python3", Qt.resolvedUrl("operator_todos.py").toString().replace(/^file:\/\//, ""), "post",
      JSON.stringify({request_key: "smoke-delivery", session_id: "00000000-0000-4000-8000-00000000abcd", title: "Smoke delivery check", kind: "approval", term: "short", important: true,
        context: "Native smoke test request.", recommendation: "Approve.", consequence: "Nothing outside the isolated test database."}), "--source", "codex"]
  }
  Timer {
    interval: 100
    running: !test.finished
    repeat: true
    onTriggered: {
      ticks++
      if (ticks > 200) { report(false, "Native smoke test timed out at stage " + stage + ": " + (panel ? panel.error : "no panel")); return }
      if (!panel || !panel.connected || panel.busy) return
      try {
        if (stage === 0) {
          check(panel.testAdd.enabled, "Add is enabled when input is empty")
          panel.testAdd.clicked()
          check(panel.testInput.focus, "Empty Add focuses the input")
          check(!panel.busy, "Empty Add creates no empty task")
          panel.testInput.text = "Native Add button test"
          panel.testAdd.clicked()
          stage = 1
        } else if (stage === 1 && panel.rows.length === 1) {
          check(panel.rows[0].title === "Native Add button test", "Add button persists the typed task")
          check(panel.testInput.text === "", "Successful Add clears input")
          firstId = panel.rows[0].id
          panel.testInput.text = "Native Enter test"
          panel.testInput.accepted()
          stage = 2
        } else if (stage === 2 && panel.rows.length === 2) {
          check(panel.rows.some(function(r) { return r.title === "Native Enter test" }), "Enter persists the typed task")
          panel.testInput.text = "SIMULATE_SAVE_FAILURE"
          panel.testAdd.clicked()
          stage = 3
        } else if (stage === 3) {
          check(panel.error.indexOf("Simulated storage error") >= 0, "Failed save displays the backend error")
          check(panel.testInput.text === "SIMULATE_SAVE_FAILURE", "Failed save retains the draft")
          check(panel.testAdd.enabled, "Add is enabled again after failure")
          panel.act(firstId, "done")
          stage = 4
        } else if (stage === 4 && panel.rows.some(function(r) { return r.id === firstId && r.status === "done" })) {
          panel.history = true
          check(panel.shown.length === 1, "Completed item appears in History")
          panel.act(firstId, "restore")
          stage = 5
        } else if (stage === 5 && panel.rows.every(function(r) { return r.status === "open" })) {
          panel.history = false
          check(panel.shown.length === 2, "Restored item returns to the active list")
          panel.run("setup-status", {})
          stage = 6
        } else if (stage === 6) {
          check(panel.agentStatus.length === 3, "Agents view reads all integration statuses")
          check(panel.testTabs.itemAt(0).text === "Short term", "Populated Short term tab has no count")
          check(panel.testTabs.itemAt(1).text === "Long term", "Long term tab has no count")
          panel.liveAgents = [{source: "codex", clients: 1}]
          check(panel.agentConnected("codex"), "Live agent gets a green connection indicator")
          check(!panel.agentConnected("claude"), "Disconnected agent has no green indicator")
          check(!panel.attentionIndicatorVisible, "A connection alone never lights the bar dot")
          panel.attention = 1
          check(panel.attentionIndicatorVisible, "Closed panel shows the attention dot")
          panel.open()
          check(!panel.attentionIndicatorVisible, "Open panel hides the outside attention dot")
          panel.close()
          check(panel.attentionIndicatorVisible, "Closing restores the dot while attention is pending")
          panel.attention = 0
          check(!panel.attentionIndicatorVisible, "Resolving attention clears the dot")
          panel.connected = false
          check(!panel.agentConnected("codex"), "Disconnected watcher cannot claim a live agent")
          panel.connected = true
          check(panel.deliveryLabel({status: "answered", delivery: "sent", unacknowledged: true, source: "codex"}).indexOf("no acknowledgement") >= 0, "Stale hand-over label asks for a retry")
          check(panel.deliveryLabel({status: "answered", delivery: "saved", source: "codex", session_id: ""}).indexOf("no conversation ID") >= 0, "Missing conversation ID is labelled")
          poster.running = true
          stage = 7
        } else if (stage === 7 && panel.rows.some(function(r) { return r.source === "codex" })) {
          var agent = panel.rows.filter(function(r) { return r.source === "codex" })[0]
          agentId = agent.id
          check(agent.session_id === "00000000-0000-4000-8000-00000000abcd", "Agent request carries its conversation ID")
          panel.act(agentId, "approve")
          stage = 8
        } else if (stage === 8 && panel.rows.some(function(r) { return r.id === agentId && r.delivery === "failed" })) {
          var failed = panel.rows.filter(function(r) { return r.id === agentId })[0]
          check(failed.response && failed.response.action === "approve", "Approving records the operator decision")
          check(!!failed.delivery_error, "Failed desktop delivery keeps its reason for the row")
          check(panel.deliveryLabel(failed).indexOf("delivery failed") >= 0, "Failed delivery is labelled as such")
          check(panel.attention >= 1, "Failed delivery lights the attention dot")
          failedAt = failed.updated_at
          panel.act(agentId, "retry")
          stage = 9
        } else if (stage === 9 && panel.rows.some(function(r) { return r.id === agentId && r.delivery === "failed" && r.updated_at > failedAt })) {
          check(true, "Retry delivery repeats the hand-over and reports the new outcome")
          report(true, "Native UI smoke checks passed")
        }
      } catch (e) { report(false, e.message) }
    }
  }
}
