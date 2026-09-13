import QtQuick
import qs.Commons
import qs.Ui

BarWidget {
  id: root
  moduleName: "portertanner.operator-todos"
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight
  readonly property bool opened: loader.item ? loader.item.opened : false
  readonly property bool popoutSwitchClosing: loader.item ? loader.item.popoutSwitchClosing : false
  function inject() {
    if (!loader.item) return
    loader.item.bar = root.bar
    loader.item.settings = root.settings
    loader.item.anchorItem = button
    loader.item.hostWidget = root
  }
  function open() { if (loader.item) loader.item.open() }
  function close() { if (loader.item) loader.item.close() }
  function toggle() { if (loader.item) loader.item.toggle() }
  function closeForPopoutSwitch() { if (loader.item) loader.item.closeForPopoutSwitch() }
  onBarChanged: inject()
  onSettingsChanged: inject()
  Loader {
    id: loader
    active: true
    visible: false
    source: Qt.resolvedUrl("TodoPanel.qml") + "?revision=" + Date.now()
    onLoaded: { root.inject(); Qt.callLater(root.inject) }
  }
  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "\uf0ae"
    fontSize: Style.font.icon
    tooltipText: loader.item && loader.item.attention > 0 ? "Agentic Operator To Do List · Needs your attention" : "Agentic Operator To Do List"
    onPressed: function(mouseButton) { if (mouseButton === Qt.LeftButton) root.toggle() }
    Accessible.role: Accessible.Button
    Accessible.name: tooltipText
    Rectangle {
      width: Style.space(5)
      height: width
      radius: width / 2
      anchors.right: parent.right
      anchors.rightMargin: Style.space(4)
      anchors.top: parent.top
      anchors.topMargin: Style.space(4)
      color: "#ef5350"
      visible: loader.item ? loader.item.attentionIndicatorVisible : false
    }
  }
}
