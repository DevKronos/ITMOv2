import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, writeFile, symlink, rm, access } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createCheckHooks, runCheck } from "../lib/python-check.mjs";
import { PythonCheckPlugin } from "../plugins/python-check.js";

const python = fileURLToPath(new URL("../../.venv/bin/python", import.meta.url));
async function fixture(t, script = "print('controlled PASS')", withPython = true) {
  const root = await mkdtemp(path.join(tmpdir(), "hook test space-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  for (const dir of ["app", "tests", "scripts", ".venv/bin", ".opencode/skills"]) await mkdir(path.join(root, dir), { recursive: true });
  if (withPython) await symlink(python, path.join(root, ".venv/bin/python"));
  await writeFile(path.join(root, "scripts/check.py"), script);
  return root;
}
const input = (tool, id = "one") => ({ tool, sessionID: "session", callID: id });
const result = (tool, file) => ({
  title: "saved", output: "Edit applied successfully.",
  metadata: tool === "write" ? { filepath: file } : { filediff: { file } },
});
async function edit(hooks, tool, file, value = "new = 1", id = "one") {
  const info = input(tool, id);
  await hooks["tool.execute.before"](info, { args: { filePath: file } });
  await writeFile(file, value);
  const output = result(tool, file);
  await hooks["tool.execute.after"](info, output);
  return output;
}

for (const [tool, dir] of [["edit", "app"], ["write", "tests"], ["write", "scripts"]]) {
  test(`${tool} ${dir}/*.py: one PASS in tool output`, async (t) => {
    const root = await fixture(t); let calls = 0;
    const hooks = createCheckHooks(root, { runner: async (cwd) => {
      assert.equal(cwd, root); calls++;
      return { status: "PASS", exitCode: 0, output: "46 passed" };
    } });
    const output = await edit(hooks, tool, path.join(root, dir, "example.py"));
    assert.equal(calls, 1);
    assert.match(output.output, /Edit applied successfully/);
    assert.match(output.output, /PASS; exit_code=0/);
    assert.match(output.output, /46 passed/);
    assert.equal(output.metadata.pythonChecks.exitCode, 0);
  });
}

test("FAIL is a rejected tool call with diagnostics; edit stays saved", async (t) => {
  const root = await fixture(t); const file = path.join(root, "app/failure.py");
  const hooks = createCheckHooks(root, { runner: async () => ({ status: "FAIL", exitCode: 1, output: "SyntaxError: controlled failure" }) });
  await assert.rejects(edit(hooks, "write", file, "broken ="), (error) => {
    assert.match(error.message, /FAIL; exit_code=1/);
    assert.match(error.message, /SyntaxError: controlled failure/);
    assert.match(error.message, /No rollback/);
    return true;
  });
  assert.equal(await readFile(file, "utf8"), "broken =");
});

test("Markdown, skill Python, outside paths and unrelated tools do not run", async (t) => {
  const root = await fixture(t); let calls = 0;
  const hooks = createCheckHooks(root, { runner: async () => { calls++; } });
  for (const file of ["CONFIG.md", "app/notes.md", ".opencode/skills/example.py", "outside.py"]) {
    await edit(hooks, "write", path.join(root, file));
  }
  for (const tool of ["read", "bash", "shell", "task", "batch", "custom"]) {
    await hooks["tool.execute.after"](input(tool), result("write", path.join(root, "app/example.py")));
  }
  assert.equal(calls, 0);
});

test("one multi-file apply_patch (including move/delete) runs once", async (t) => {
  const root = await fixture(t); let calls = 0;
  const a = path.join(root, "app/a.py"), b = path.join(root, "tests/b.py"), c = path.join(root, "scripts/c.py");
  await writeFile(a, "old = 1"); await writeFile(c, "old = 2");
  const hooks = createCheckHooks(root, { runner: async () => { calls++; return { status: "PASS", exitCode: 0, output: "OK" }; } });
  const info = input("apply_patch");
  await hooks["tool.execute.before"](info, { args: { patchText: "*** Begin Patch\n*** Update File: app/a.py\n*** Move to: tests/b.py\n@@\n-old = 1\n+new = 1\n*** Delete File: scripts/c.py\n*** End Patch" } });
  await rm(a); await rm(c); await writeFile(b, "new = 1");
  const output = { output: "Success", metadata: { files: [{ filePath: a, movePath: b }, { filePath: c }, { filePath: path.join(root, "NOTES.md") }] } };
  await hooks["tool.execute.after"](info, output);
  assert.equal(calls, 1);
  assert.match(output.output, /PASS/);
});

test("unchanged write and failed edit (no success metadata) do not run", async (t) => {
  const root = await fixture(t); let calls = 0;
  const hooks = createCheckHooks(root, { runner: async () => { calls++; } });
  const file = path.join(root, "app/example.py");
  await writeFile(file, "same = 1");
  await edit(hooks, "write", file, "same = 1");
  const info = input("edit", "failed");
  await hooks["tool.execute.before"](info, { args: { filePath: file } });
  // OpenCode does not emit after on a failed edit; malformed after is ignored too.
  await hooks["tool.execute.after"](info, { output: "error", metadata: {} });
  assert.equal(calls, 0);
});

test("symlink escape is excluded", async (t) => {
  const root = await fixture(t); const outside = await fixture(t); let calls = 0;
  await symlink(path.join(outside, "app"), path.join(root, "app/link"));
  const hooks = createCheckHooks(root, { runner: async () => { calls++; } });
  await edit(hooks, "write", path.join(root, "app/link/external.py"));
  assert.equal(calls, 0);
});

test("different tool calls serialize checks and both receive results", async (t) => {
  const root = await fixture(t); let active = 0, max = 0, count = 0;
  const hooks = createCheckHooks(root, { runner: async () => {
    active++; max = Math.max(max, active); count++;
    await new Promise((resolve) => setImmediate(resolve));
    active--; return { status: "PASS", exitCode: 0, output: "OK" };
  } });
  const outputs = await Promise.all([edit(hooks, "write", path.join(root, "app/a.py"), "a=1", "a"), edit(hooks, "write", path.join(root, "tests/b.py"), "b=1", "b")]);
  assert.equal(max, 1); assert.equal(count, 2);
  assert(outputs.every((out) => out.output.includes("PASS")));
});

test("runner uses cwd, temporary database and offline environment", async (t) => {
  const root = await fixture(t, "import os,json,pathlib\np=pathlib.Path(os.environ['APP_DB_PATH']); p.touch()\nprint(json.dumps({'cwd':os.getcwd(),'db':str(p),'background':os.environ['APP_BACKGROUND'],'snapshots':os.environ.get('APP_SNAPSHOT_DIR')}))");
  const checked = await runCheck(root);
  assert.equal(checked.status, "PASS"); assert.equal(checked.exitCode, 0);
  const env = JSON.parse(checked.output);
  assert.equal(env.cwd, root); assert.equal(env.background, "0"); assert.equal(env.snapshots, null);
  assert(!env.db.startsWith(root));
  await assert.rejects(access(env.db));
});

test("runner reports missing Python without a false PASS", async (t) => {
  const root = await fixture(t, "pass", false);
  const output = await runCheck(root);
  assert.equal(output.status, "FAIL"); assert.equal(output.exitCode, 127);
  assert.match(output.reason, /ENOENT/);
});

test("runner limits diagnostics and preserves failing tail", async (t) => {
  const root = await fixture(t, "import sys\nprint('x'*30000)\nprint('useful failure tail',file=sys.stderr)\nsys.exit(7)");
  const output = await runCheck(root);
  assert.equal(output.status, "FAIL"); assert.equal(output.exitCode, 7);
  assert(output.output.length < 16100); assert.match(output.output, /truncated/);
  assert.match(output.output, /useful failure tail/);
});

test("timeout kills Python and its child process group", async (t) => {
  const root = await fixture(t, "import subprocess,sys,pathlib,time\np=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])\npathlib.Path('child.pid').write_text(str(p.pid))\ntime.sleep(30)");
  const output = await runCheck(root, { timeoutMs: 600 });
  assert.equal(output.status, "FAIL"); assert.equal(output.exitCode, 124);
  assert.match(output.reason, /Timeout.*SIGKILL/);
  const pid = (await readFile(path.join(root, "child.pid"), "utf8")).trim();
  try {
    const stat = await readFile(`/proc/${pid}/stat`, "utf8");
    assert.match(stat, /\) Z /, "child must be terminated (zombie awaiting reaping is not running)");
  } catch (error) { if (error.code !== "ENOENT") throw error; }
});

test("plugin factory exposes only supported hook contracts", async () => {
  const hooks = await PythonCheckPlugin({ directory: process.cwd() });
  assert.deepEqual(Object.keys(hooks).sort(), ["tool.execute.after", "tool.execute.before"]);
});
