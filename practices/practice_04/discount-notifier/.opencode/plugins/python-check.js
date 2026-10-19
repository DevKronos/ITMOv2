import { fileURLToPath } from "node:url";
import { createCheckHooks } from "../lib/python-check.mjs";

// Resolve the application, not the enclosing ITMOv2 git worktree.
const root = fileURLToPath(new URL("../../", import.meta.url));
export const PythonCheckPlugin = async ({ directory }) =>
  createCheckHooks(root, { directory });
