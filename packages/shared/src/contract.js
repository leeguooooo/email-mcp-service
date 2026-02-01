const { printJson } = require("./json");

function parseGlobalFlags(argv) {
  const rest = [];
  let asJson = false;
  let pretty = false;

  for (const arg of argv) {
    if (arg === "--json") {
      asJson = true;
      continue;
    }
    if (arg === "--pretty") {
      pretty = true;
      continue;
    }
    rest.push(arg);
  }

  return { asJson, pretty, argv: rest };
}

function ensureSuccessField(result) {
  if (!result || typeof result !== "object") return { success: false, error: "Invalid result" };
  if (typeof result.success === "boolean") return result;
  result.success = !result.error;
  return result;
}

function exitCodeForResult(result) {
  const r = ensureSuccessField(result);
  return r.success ? 0 : 1;
}

function handleJsonOrText({ result, asJson, pretty, printText }) {
  const normalized = ensureSuccessField(result);

  if (asJson) {
    printJson(normalized, pretty);
  } else if (typeof printText === "function") {
    printText(normalized);
  } else {
    // Default: print JSON even when not requested (debug-friendly).
    printJson(normalized, true);
  }

  return exitCodeForResult(normalized);
}

function invalidUsage({ message, asJson, pretty }) {
  const payload = { success: false, error: message || "Invalid usage" };
  if (asJson) {
    printJson(payload, pretty);
  } else {
    process.stderr.write((payload.error || "Invalid usage") + "\n");
  }
  return 2;
}

module.exports = {
  parseGlobalFlags,
  ensureSuccessField,
  exitCodeForResult,
  handleJsonOrText,
  invalidUsage,
};
