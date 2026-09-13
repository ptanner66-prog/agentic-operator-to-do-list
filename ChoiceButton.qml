import QtQuick
import qs.Commons

Rectangle {
  id: root
  property string text: ""
  property color foreground: Color.foreground
  signal clicked()
  implicitHeight: label.implicitHeight + Style.space(16)
  radius: Style.cornerRadius
  color: mouse.containsMouse || activeFocus ? Qt.alpha(foreground, 0.1) : "transparent"
  border.width: 1
  border.color: Qt.alpha(foreground, activeFocus ? 0.8 : 0.2)
  opacity: enabled ? 1 : 0.5
  activeFocusOnTab: true
  Accessible.role: Accessible.Button
  Accessible.name: text
  Keys.onReturnPressed: root.clicked()
  Keys.onSpacePressed: root.clicked()
  Text {
    id: label
    anchors.centerIn: parent
    width: parent.width - Style.space(18)
    text: root.text
    textFormat: Text.PlainText
    wrapMode: Text.Wrap
    color: root.foreground
    font.family: Style.font.family
    font.pixelSize: Style.font.body
  }
  MouseArea { id: mouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.clicked() }
}
