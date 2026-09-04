import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import "Model.js" as Model

Panel {
  id: root
  moduleName: "omaantigravity"
  ipcTarget: "omaantigravity"
  manageIpc: false

  // ── State Properties ────────────────────────────────────────────────────────
  property var usageData: ({ status: "loading", groups: [], overall: { lowest_remaining_pct: 100 } })
  property bool loading: fetchProc.running
  property int dataVersion: 0

  // ── Settings ────────────────────────────────────────────────────────────────
  property int pollIntervalSec: 300
  property bool showPercentageInBar: true
  property string barMetric: "lowest"

  // ── Theme / Palette ─────────────────────────────────────────────────────────
  readonly property color fg: root.bar ? root.bar.foreground : Color.foreground
  readonly property color dim: Qt.darker(fg, 1.45)
  readonly property color subtle: Qt.rgba(fg.r, fg.g, fg.b, 0.08)
  readonly property color borderCol: Qt.rgba(fg.r, fg.g, fg.b, 0.12)
  readonly property color urgent: root.bar ? root.bar.urgent : Color.urgent
  readonly property color warning: "#e5a50a"
  readonly property color track: Style.selectedFillFor(fg, Color.accent)
  readonly property string fontFamily: root.bar ? root.bar.fontFamily : Style.font.family

  // ── Helpers ─────────────────────────────────────────────────────────────────
  function setting(name, fallback) {
    var value = settings ? settings[name] : undefined
    return value === undefined || value === null ? fallback : value
  }

  function applySettings() {
    pollIntervalSec = Math.max(30, Math.min(3600, setting("pollIntervalSec", 300)))
    pollTimer.interval = pollIntervalSec * 1000
    showPercentageInBar = setting("showPercentageInBar", true)
    barMetric = setting("barMetric", "lowest")
  }

  function pathFromUrl(url) {
    var value = String(url || "")
    if (value.indexOf("file://") === 0)
      return decodeURIComponent(value.substring(7))
    return value
  }

  function refresh(force) {
    if (fetchProc.running) return
    var scriptPath = pathFromUrl(Qt.resolvedUrl("scripts/fetch_usage.py"))
    var args = ["python3", scriptPath]
    if (force) args.push("--force")
    else args.push("--cached")
    fetchProc.command = args
    fetchProc.running = true
  }

  function loadInitialCache() {
    var scriptPath = pathFromUrl(Qt.resolvedUrl("scripts/fetch_usage.py"))
    cacheProc.command = ["python3", scriptPath, "--cached-only"]
    cacheProc.running = true
  }

  function triggerPress(b) {
    if (b === Qt.MiddleButton || b === Qt.RightButton) {
      refresh(true)
      return
    }
    if (opened) close()
    else {
      open()
      refresh(false)
    }
  }

  function state() {
    return JSON.stringify(root.usageData)
  }

  visible: true
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  Component.onCompleted: {
    applySettings()
    loadInitialCache()
    refresh(false)
  }

  onSettingsChanged: applySettings()

  onOpenedChanged: {
    if (opened) refresh(false)
  }

  // ── Processes ───────────────────────────────────────────────────────────────
  Process {
    id: cacheProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var raw = String(text || "").trim()
        if (raw.length > 0 && raw.indexOf("{") === 0) {
          var parsed = Model.parseData(raw)
          if (parsed && parsed.status === "ok") {
            root.usageData = parsed
            root.dataVersion++
          }
        }
      }
    }
  }

  Process {
    id: fetchProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var raw = String(text || "").trim()
        if (raw.length > 0 && raw.indexOf("{") === 0) {
          root.usageData = Model.parseData(raw)
          root.dataVersion++
        }
      }
    }
  }

  // ── Background Polling Timer ────────────────────────────────────────────────
  Timer {
    id: pollTimer
    interval: root.pollIntervalSec * 1000
    running: true
    repeat: true
    onTriggered: root.refresh(false)
  }

  // ── IPC Handler ─────────────────────────────────────────────────────────────
  IpcHandler {
    target: "omaantigravity"

    function refresh() { root.refresh(true) }
    function open() { root.open() }
    function close() { root.close() }
    function toggle() { root.opened ? root.close() : root.open() }
    function state() { return root.state() }
  }

  // ── Bar Button ──────────────────────────────────────────────────────────────
  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    labelVisible: false
    fixedWidth: root.showPercentageInBar ? (contentRow.implicitWidth + scaledHorizontalMargin * 2) : (root.bar && root.bar.vertical ? -1 : Style.space(28))
    fixedHeight: root.bar && root.bar.vertical ? Style.space(28) : -1
    tooltipText: root.usageData && root.usageData.tooltip ? root.usageData.tooltip : "Antigravity CLI Quota"
    onPressed: function(b) { root.triggerPress(b) }

    Row {
      id: contentRow
      anchors.centerIn: parent
      spacing: Style.space(6)

      Image {
        id: barLogo
        width: Style.space(16)
        height: Style.space(16)
        anchors.verticalCenter: parent.verticalCenter
        source: Qt.resolvedUrl("assets/antigravity.png")
        fillMode: Image.PreserveAspectFit
        smooth: true
        mipmap: true
      }

      Text {
        visible: root.showPercentageInBar
        anchors.verticalCenter: parent.verticalCenter
        text: {
          var v = Model.getMetricValue(root.usageData, root.barMetric)
          return v === "--" ? "--" : (v + "%")
        }
        color: root.bar ? root.bar.barForeground : root.fg
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
        renderType: Text.NativeRendering
      }
    }
  }

  // ── Panel Overlay ───────────────────────────────────────────────────────────
  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(480))
    contentHeight: panel.fittedContentHeight(flickableContent.implicitHeight, Style.space(580))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()
      onTextKey: function(t) {
        if (t === "r" || t === "R") root.refresh(true)
      }

      Flickable {
        id: panelFlick
        anchors.fill: parent
        contentWidth: width
        contentHeight: flickableContent.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.VerticalFlick

        ColumnLayout {
          id: flickableContent
          width: panelFlick.width
          spacing: Style.space(12)

          // ── Panel Hero Header ──────────────────────────────────────────────
          PanelHero {
            Layout.fillWidth: true
            title: "Antigravity Quota"
            meta: {
              var parts = []
              if (root.usageData.active_model && root.usageData.active_model.label) {
                parts.push(root.usageData.active_model.label)
              }
              if (root.usageData.last_updated) {
                parts.push("Updated " + root.usageData.last_updated)
              } else if (root.loading) {
                parts.push("Updating...")
              }
              return parts.length > 0 ? parts.join(" · ") : "Google Antigravity CLI"
            }
            foreground: root.fg
            fontFamily: root.fontFamily
            iconOpacity: 1.0
            iconComponent: Component {
              Image {
                anchors.centerIn: parent
                width: Style.font.display
                height: Style.font.display
                source: Qt.resolvedUrl("assets/antigravity.png")
                fillMode: Image.PreserveAspectFit
                smooth: true
                mipmap: true
              }
            }
            trailingControl: Component {
              RowLayout {
                spacing: Style.space(6)
                anchors.verticalCenter: parent.verticalCenter

                Button {
                  text: root.loading ? "Refreshing..." : "Refresh"
                  foreground: root.fg
                  fontFamily: root.fontFamily
                  fontSize: Style.font.caption
                  horizontalPadding: Style.spacing.controlPaddingX
                  verticalPadding: Style.spacing.controlPaddingY
                  onClicked: root.refresh(true)
                }
              }
            }
          }

          PanelSeparator {
            Layout.fillWidth: true
            foreground: root.fg
          }

          // ── Error View ─────────────────────────────────────────────────────
          BorderSurface {
            visible: root.usageData && root.usageData.status === "error"
            Layout.fillWidth: true
            color: Qt.rgba(root.urgent.r, root.urgent.g, root.urgent.b, 0.1)
            borderSpec: Border.flat(root.urgent, 1)
            radius: Style.cornerRadius
            padding: Style.space(12)

            ColumnLayout {
              anchors.left: parent.left
              anchors.right: parent.right
              anchors.top: parent.top
              spacing: Style.space(6)

              RowLayout {
                spacing: Style.space(8)
                Text {
                  text: "󰀨"
                  color: root.urgent
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.title
                }
                Text {
                  text: "Antigravity CLI Error"
                  color: root.fg
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.body
                  font.bold: true
                }
              }

              Text {
                Layout.fillWidth: true
                text: root.usageData.error || "Unable to communicate with Antigravity CLI."
                color: root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                wrapMode: Text.WordWrap
              }

              Button {
                Layout.topMargin: Style.space(4)
                text: "Retry Now"
                foreground: root.fg
                fontFamily: root.fontFamily
                fontSize: Style.font.caption
                horizontalPadding: Style.spacing.controlPaddingX
                verticalPadding: Style.spacing.controlPaddingY
                onClicked: root.refresh(true)
              }
            }
          }

          // ── Stale Cache Warning ────────────────────────────────────────────
          BorderSurface {
            visible: !!root.usageData.stale
            Layout.fillWidth: true
            color: Qt.rgba(root.warning.r || 0.9, root.warning.g || 0.6, 0, 0.08)
            borderSpec: Border.flat(root.warning, 1)
            radius: Style.cornerRadius
            padding: Style.space(8)

            RowLayout {
              anchors.fill: parent
              spacing: Style.space(8)

              Text {
                text: "󰅐"
                color: root.warning
                font.family: root.fontFamily
                font.pixelSize: Style.font.body
              }

              Text {
                Layout.fillWidth: true
                text: "Showing cached limits. A fresh background update is in progress."
                color: root.fg
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                wrapMode: Text.WordWrap
              }
            }
          }

          // ── Model Groups Repeater ──────────────────────────────────────────
          Repeater {
            model: root.usageData && root.usageData.groups ? root.usageData.groups : []

            delegate: BorderSurface {
              required property var modelData
              required property int index

              Layout.fillWidth: true
              color: root.subtle
              borderSpec: Border.flat(root.borderCol, 1)
              radius: Style.cornerRadius
              padding: Style.space(12)
              implicitHeight: groupBody.implicitHeight + contentTopInset + contentBottomInset

              ColumnLayout {
                id: groupBody
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: Style.space(12)
                spacing: Style.space(12)

                // Group Header
                RowLayout {
                  Layout.fillWidth: true
                  spacing: Style.space(8)

                  Text {
                    text: modelData.icon || "󰚩"
                    color: root.fg
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.title
                    Layout.alignment: Qt.AlignVCenter
                  }

                  ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2

                    Text {
                      text: modelData.name || "Model Group"
                      color: root.fg
                      font.family: root.fontFamily
                      font.pixelSize: Style.font.body
                      font.bold: true
                    }

                    Text {
                      text: modelData.description || ""
                      color: root.dim
                      font.family: root.fontFamily
                      font.pixelSize: Style.font.caption
                      elide: Text.ElideRight
                      Layout.fillWidth: true
                      visible: text !== ""
                    }
                  }
                }

                // Buckets Repeater
                Repeater {
                  model: modelData.buckets || []

                  delegate: ColumnLayout {
                    required property var modelData
                    required property int index

                    Layout.fillWidth: true
                    spacing: Style.space(4)

                    // Bucket Labels Row
                    RowLayout {
                      Layout.fillWidth: true
                      spacing: Style.space(8)

                      Text {
                        text: modelData.window_title || modelData.name || "Limit"
                        color: root.fg
                        font.family: root.fontFamily
                        font.pixelSize: Style.font.bodySmall
                        font.bold: true
                      }

                      Item { Layout.fillWidth: true }

                      // Reset Countdown Badge
                      RowLayout {
                        spacing: Style.space(3)
                        visible: modelData.reset_countdown !== ""

                        Text {
                          text: "󰅐"
                          color: root.dim
                          font.family: root.fontFamily
                          font.pixelSize: Style.font.caption
                        }

                        Text {
                          text: "Resets in " + modelData.reset_countdown
                          color: root.dim
                          font.family: root.fontFamily
                          font.pixelSize: Style.font.caption
                        }
                      }

                      // Remaining Percentage
                      Text {
                        text: modelData.remaining_pct + "% remaining"
                        color: Model.getStatusColor(modelData.remaining_pct, root.fg, root.urgent, root.warning)
                        font.family: root.fontFamily
                        font.pixelSize: Style.font.bodySmall
                        font.bold: true
                      }
                    }

                    // Rounded Meter Bar
                    Item {
                      id: meterItem
                      Layout.fillWidth: true
                      implicitHeight: Style.space(8)

                      Rectangle {
                        id: trackRect
                        anchors.fill: parent
                        radius: height / 2
                        color: root.track
                      }

                      Rectangle {
                        anchors.left: trackRect.left
                        anchors.verticalCenter: trackRect.verticalCenter
                        height: trackRect.height
                        radius: trackRect.radius
                        width: trackRect.width * Math.max(0, Math.min(1, modelData.remaining_fraction))
                        color: Model.getStatusColor(modelData.remaining_pct, root.fg, root.urgent, root.warning)

                        Behavior on width {
                          NumberAnimation { duration: 250; easing.type: Easing.OutCubic }
                        }
                      }
                    }

                    // Optional description/hint
                    Text {
                      visible: modelData.description !== ""
                      Layout.fillWidth: true
                      text: modelData.description
                      color: root.dim
                      font.family: root.fontFamily
                      font.pixelSize: Style.font.caption
                      wrapMode: Text.WordWrap
                      opacity: 0.85
                    }

                    Item {
                      height: Style.space(4)
                      visible: index < (modelData.buckets ? modelData.buckets.length - 1 : 0)
                    }
                  }
                }
              }
            }
          }

          // ── Info Card (Explanation of Limits) ──────────────────────────────
          BorderSurface {
            visible: root.usageData && root.usageData.description !== undefined && root.usageData.description !== ""
            Layout.fillWidth: true
            color: root.subtle
            borderSpec: Border.flat(root.borderCol, 1)
            radius: Style.cornerRadius
            padding: Style.space(12)
            implicitHeight: infoLayout.implicitHeight + contentTopInset + contentBottomInset

            RowLayout {
              id: infoLayout
              anchors.left: parent.left
              anchors.right: parent.right
              anchors.top: parent.top
              anchors.margins: Style.space(12)
              spacing: Style.space(10)

              Text {
                text: "󰌵"
                color: root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.body
                Layout.alignment: Qt.AlignTop
              }

              Text {
                Layout.fillWidth: true
                text: root.usageData.description || ""
                color: root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                wrapMode: Text.WordWrap
                lineHeight: 1.25
              }
            }
          }

          // ── Footer / Keyboard Shortcuts ────────────────────────────────────
          RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: Style.space(2)
            Layout.bottomMargin: Style.space(8)

            Text {
              text: "Shortcuts: [R] Refresh · [Esc] Close"
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              opacity: 0.7
            }

            Item { Layout.fillWidth: true }

            Text {
              text: "omarchy / antigravity"
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              opacity: 0.5
            }
          }
        }
      }
    }
  }
}
