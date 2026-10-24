function formatDateTime(value) {
  if (!value) return ''
  return String(value).slice(0, 16).replace('T', ' ')
}

function formatDate(value) {
  if (!value) return ''
  return String(value).slice(0, 10)
}

module.exports = { formatDateTime, formatDate }
