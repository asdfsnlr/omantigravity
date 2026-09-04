// OmaAntigravity Model.js
// Data helpers and formatting utilities for the Antigravity usage panel

function parseData(raw) {
  try {
    var data = JSON.parse(String(raw || "{}"))
    if (typeof data !== "object" || data === null) {
      return { status: "empty", groups: [], overall: { lowest_remaining_pct: 100 } }
    }
    return data
  } catch (e) {
    return { status: "error", error: "Failed to parse usage data", groups: [] }
  }
}

function getMetricValue(data, metricKey) {
  if (!data || !data.groups || !Array.isArray(data.groups) || data.groups.length === 0) {
    return "--"
  }
  
  if (!metricKey || metricKey === "lowest") {
    if (data.overall && typeof data.overall.lowest_remaining_pct === "number") {
      return data.overall.lowest_remaining_pct
    }
    return "--"
  }

  for (var i = 0; i < data.groups.length; i++) {
    var grp = data.groups[i]
    var buckets = grp.buckets || []
    for (var j = 0; j < buckets.length; j++) {
      var b = buckets[j]
      if (b.id === metricKey || b.window === metricKey) {
        return b.remaining_pct !== undefined ? b.remaining_pct : 100
      }
    }
  }

  return (data.overall && typeof data.overall.lowest_remaining_pct === "number") 
    ? data.overall.lowest_remaining_pct 
    : 100
}

function formatBarText(data, showPercentage, barIcon, metricKey) {
  var icon = barIcon || "󰒋"
  if (!showPercentage) {
    return icon
  }
  if (!data || !data.groups || data.groups.length === 0) {
    return icon
  }
  var val = getMetricValue(data, metricKey)
  return icon + " " + val + "%"
}

function getStatusColor(remainingPct, fg, urgentColor, warningColor) {
  if (remainingPct <= 15) {
    return urgentColor
  }
  if (remainingPct <= 30) {
    return warningColor
  }
  return fg
}

function timeAgo(timestamp) {
  if (!timestamp) return ""
  var now = Math.floor(Date.now() / 1000)
  var diff = Math.max(0, now - timestamp)
  if (diff < 60) return "just now"
  var mins = Math.floor(diff / 60)
  if (mins < 60) return mins + "m ago"
  var hrs = Math.floor(mins / 60)
  return hrs + "h ago"
}
