function safeJsonStringify(value, pretty) {
  return JSON.stringify(value, null, pretty ? 2 : 0);
}

function printJson(value, pretty) {
  process.stdout.write(safeJsonStringify(value, pretty) + "\n");
}

module.exports = {
  printJson,
  safeJsonStringify,
};
