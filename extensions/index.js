import { execFile } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { Type } from "typebox";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");

function runCmanPiSessions(args, signal) {
  return new Promise((resolvePromise, reject) => {
    const child = execFile(
      "python3",
      [resolve(ROOT, "scripts", "pi_sessions.py"), ...args],
      {
        cwd: ROOT,
        signal,
        maxBuffer: 1024 * 1024 * 8,
      },
      (error, stdout, stderr) => {
        if (error) {
          reject(new Error(stderr || error.message));
          return;
        }
        resolvePromise(stdout.trim() || stderr.trim());
      },
    );

    child.stdin?.end();
  });
}

export default function (pi) {
  pi.registerTool({
    name: "cman_pi_sessions",
    label: "cman Pi Sessions",
    description: "List or search Pi Coding Agent JSONL session logs using cman.",
    promptSnippet: "Use cman_pi_sessions to inspect local Pi Coding Agent session logs.",
    promptGuidelines: [
      "Use this tool when the user asks to remember, search, or summarize past Pi Coding Agent sessions.",
      "The tool reads local ~/.pi/agent/sessions logs and returns resume commands with pi --session.",
    ],
    parameters: Type.Object({
      query: Type.Optional(Type.String({ description: "Search keyword. Omit to list recent Pi sessions." })),
      limit: Type.Optional(Type.Number({ description: "Maximum sessions to return. Default: 10." })),
      path: Type.Optional(Type.String({ description: "Optional Pi sessions directory override." })),
    }),
    async execute(_toolCallId, params, signal) {
      const limit = Math.max(1, Math.min(100, Math.floor(params.limit ?? 10)));
      const args = [];

      if (params.query?.trim()) {
        args.push(params.query.trim());
      }
      args.push("-n", String(limit));
      if (params.path?.trim()) {
        args.push("--path", params.path.trim());
      }

      try {
        const output = await runCmanPiSessions(args, signal);
        return {
          content: [{ type: "text", text: output }],
          details: {
            source: "cman",
            command: ["python3", "scripts/pi_sessions.py", ...args],
          },
        };
      } catch (error) {
        return {
          isError: true,
          content: [{ type: "text", text: `cman_pi_sessions failed: ${error.message}` }],
          details: {
            source: "cman",
            command: ["python3", "scripts/pi_sessions.py", ...args],
          },
        };
      }
    },
  });

  pi.registerCommand("cman-pi", {
    description: "List or search Pi sessions via cman: /cman-pi [query]",
    handler: async (args, ctx) => {
      try {
        const commandArgs = args.trim() ? [args.trim(), "-n", "10"] : ["-n", "10"];
        const output = await runCmanPiSessions(commandArgs, ctx.signal);
        ctx.ui.notify(output, "info");
      } catch (error) {
        ctx.ui.notify(`cman-pi failed: ${error.message}`, "error");
      }
    },
  });
}
