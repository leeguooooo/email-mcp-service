#!/usr/bin/env node

const { main } = require("../src/main");

Promise.resolve()
  .then(async () => {
    const argv = process.argv.slice(2);
    return await main(argv);
  })
  .then((code) => {
    process.exit(typeof code === "number" ? code : 0);
  })
  .catch((err) => {
    const msg = err && err.message ? err.message : String(err || "Error");
    process.stderr.write(msg + "\n");
    process.exit(1);
  });
