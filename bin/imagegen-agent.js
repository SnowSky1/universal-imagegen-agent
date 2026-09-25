#!/usr/bin/env node

import { main } from "../node/cli.js";

process.exitCode = await main(process.argv.slice(2));
