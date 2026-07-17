import { execFile } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, resolve, relative, isAbsolute } from "node:path";
import { homedir } from "node:os";
import { Type } from "typebox";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
let pythonCommandPromise;

function isPathInside(child, parent) {
  const rel = relative(resolve(parent), resolve(child));
  return rel === "" || (!rel.startsWith("..") && !isAbsolute(rel));
}

function assertSafeOverridePath(inputPath, roots, label) {
  if (!inputPath?.trim()) return;
  if (process.env.CMAN_ALLOW_ARBITRARY_PATH === "1") return;

  const target = resolve(inputPath.trim());
  const allowedRoots = roots.map((root) => resolve(root));
  if (!allowedRoots.some((root) => isPathInside(target, root))) {
    throw new Error(
      `${label} must be inside ${allowedRoots.join(" or ")}. ` +
        "Set CMAN_ALLOW_ARBITRARY_PATH=1 to override.",
    );
  }
}

function claudeProjectsRoot() {
  const claudeDir = process.env.CMAN_CLAUDE_DIR || resolve(homedir(), ".claude");
  return process.env.CMAN_CLAUDE_PROJECTS_DIR || resolve(claudeDir, "projects");
}

function piSessionsRoot() {
  const piAgentDir = process.env.CMAN_PI_AGENT_DIR || resolve(homedir(), ".pi", "agent");
  return process.env.CMAN_PI_SESSIONS_DIR || resolve(piAgentDir, "sessions");
}

function execFileText(command, args, options = {}) {
  return new Promise((resolvePromise, reject) => {
    const child = execFile(
      command,
      args,
      {
        cwd: ROOT,
        maxBuffer: 1024 * 1024 * 8,
        ...options,
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

async function commandWorks(command) {
  try {
    await execFileText(command, ["--version"]);
    return true;
  } catch {
    return false;
  }
}

async function resolvePythonCommand() {
  if (!pythonCommandPromise) {
    pythonCommandPromise = (async () => {
      const candidates = [
        process.env.CMAN_PYTHON,
        process.env.PYTHON,
        "python3",
        "python",
      ].filter(Boolean);

      for (const command of [...new Set(candidates)]) {
        if (await commandWorks(command)) {
          return command;
        }
      }

      throw new Error(
        "Python interpreter not found. Set CMAN_PYTHON to a Python 3 executable.",
      );
    })();
  }
  return pythonCommandPromise;
}

async function runCmanPiSessions(args, signal) {
  const pythonCommand = await resolvePythonCommand();
  const output = await execFileText(
    pythonCommand,
    [resolve(ROOT, "scripts", "pi_sessions.py"), ...args],
    { signal },
  );
  return { output, pythonCommand };
}

async function runCmanClaudeSessions(args, signal) {
  const pythonCommand = await resolvePythonCommand();
  const output = await execFileText(
    pythonCommand,
    [resolve(ROOT, "scripts", "sessions.py"), ...args],
    { signal },
  );
  return { output, pythonCommand };
}

async function runCmanSearchAll(args, signal) {
  const pythonCommand = await resolvePythonCommand();
  const output = await execFileText(
    pythonCommand,
    [resolve(ROOT, "scripts", "search_all.py"), ...args],
    { signal },
  );
  return { output, pythonCommand };
}

export default function (pi) {
  pi.registerTool({
    name: "cman_claude_sessions",
    label: "cman Claude Sessions",
    description: "List recent Claude Code JSONL session logs using cman.",
    promptSnippet: "Use cman_claude_sessions to inspect recent local Claude Code sessions.",
    promptGuidelines: [
      "Use this tool when the user asks for recent Claude Code work, a Claude Code recap, or what they did today/yesterday in Claude Code.",
      "For date recaps, pass since=today or since=yesterday instead of searching for the date as a keyword or using shell commands.",
      "The tool reads local ~/.claude/projects logs and returns resume commands with claude --resume.",
    ],
    parameters: Type.Object({
      limit: Type.Optional(Type.Number({ description: "Maximum sessions to return. Default: 10." })),
      since: Type.Optional(Type.String({ description: "Only show sessions modified since today, yesterday, YYYY-MM-DD, or YYYY-MM-DD HH:MM:SS." })),
      path: Type.Optional(Type.String({ description: "Optional Claude projects directory override." })),
      excludeSubagents: Type.Optional(Type.Boolean({ description: "Skip sub-agent sessions. Default: true." })),
    }),
    async execute(_toolCallId, params, signal) {
      const limit = Math.max(1, Math.min(100, Math.floor(params.limit ?? 10)));
      const args = ["-n", String(limit)];

      if (params.excludeSubagents !== false) {
        args.push("--exclude-subagents");
      }
      if (params.since?.trim()) {
        args.push("--since", params.since.trim());
      }
      if (params.path?.trim()) {
        assertSafeOverridePath(params.path, [claudeProjectsRoot()], "path");
        args.push("--path", params.path.trim());
      }

      try {
        const { output, pythonCommand } = await runCmanClaudeSessions(args, signal);
        return {
          content: [{ type: "text", text: output }],
          details: {
            source: "cman",
            command: [pythonCommand, "scripts/sessions.py", ...args],
          },
        };
      } catch (error) {
        return {
          isError: true,
          content: [{ type: "text", text: `cman_claude_sessions failed: ${error.message}` }],
          details: {
            source: "cman",
            command: ["<python>", "scripts/sessions.py", ...args],
          },
        };
      }
    },
  });

  pi.registerTool({
    name: "cman_pi_sessions",
    label: "cman Pi Sessions",
    description: "List or search Pi Coding Agent JSONL session logs using cman.",
    promptSnippet: "Use cman_pi_sessions to inspect local Pi Coding Agent session logs.",
    promptGuidelines: [
      "Use this tool when the user asks to remember, search, or summarize past Pi Coding Agent sessions.",
      "For date recaps, pass since=today or since=yesterday instead of searching for the date as a keyword or using shell commands.",
      "The tool reads local ~/.pi/agent/sessions logs and returns resume commands with pi --session.",
    ],
    parameters: Type.Object({
      query: Type.Optional(Type.String({ description: "Search keyword. Omit to list recent Pi sessions." })),
      limit: Type.Optional(Type.Number({ description: "Maximum sessions to return. Default: 10." })),
      since: Type.Optional(Type.String({ description: "Only show/search sessions modified since today, yesterday, YYYY-MM-DD, or YYYY-MM-DD HH:MM:SS." })),
      path: Type.Optional(Type.String({ description: "Optional Pi sessions directory override." })),
    }),
    async execute(_toolCallId, params, signal) {
      const limit = Math.max(1, Math.min(100, Math.floor(params.limit ?? 10)));
      const args = [];

      if (params.query?.trim()) {
        args.push(params.query.trim());
      }
      args.push("-n", String(limit));
      if (params.since?.trim()) {
        args.push("--since", params.since.trim());
      }
      if (params.path?.trim()) {
        assertSafeOverridePath(params.path, [piSessionsRoot()], "path");
        args.push("--path", params.path.trim());
      }

      try {
        const { output, pythonCommand } = await runCmanPiSessions(args, signal);
        return {
          content: [{ type: "text", text: output }],
          details: {
            source: "cman",
            command: [pythonCommand, "scripts/pi_sessions.py", ...args],
          },
        };
      } catch (error) {
        return {
          isError: true,
          content: [{ type: "text", text: `cman_pi_sessions failed: ${error.message}` }],
          details: {
            source: "cman",
            command: ["<python>", "scripts/pi_sessions.py", ...args],
          },
        };
      }
    },
  });

  pi.registerTool({
    name: "cman_search_all",
    label: "cman Search All",
    description: "Cross-search cman memory across Claude Code, Pi, Codex, and memory files.",
    promptSnippet: "Use cman_search_all to search past coding-agent work without asking which agent produced it.",
    promptGuidelines: [
      "Use this tool by default when the user asks what they did before, asks to remember something, or searches past work without naming a specific agent.",
      "Do not ask the user which coding agent to search first; this tool searches all supported sources.",
      "If the user names Claude Code, Pi, or Codex, set source to that agent.",
    ],
    parameters: Type.Object({
      query: Type.String({ description: "Search keyword or multi-word query" }),
      limit: Type.Optional(Type.Number({ description: "Maximum results to return. Default: 10." })),
      includeMemory: Type.Optional(Type.Boolean({ description: "Include Claude memory files. Default: true." })),
      source: Type.Optional(Type.String({ description: "Restrict source: all, claude, pi, codex, or memory. Default: all." })),
      claudePath: Type.Optional(Type.String({ description: "Optional Claude projects directory override." })),
      piPath: Type.Optional(Type.String({ description: "Optional Pi sessions directory override." })),
    }),
    async execute(_toolCallId, params, signal) {
      const limit = Math.max(1, Math.min(100, Math.floor(params.limit ?? 10)));
      const args = [params.query, "-n", String(limit)];

      if (params.includeMemory === false) {
        args.push("--no-memory");
      }
      if (params.source?.trim()) {
        args.push("--source", params.source.trim());
      }
      if (params.claudePath?.trim()) {
        assertSafeOverridePath(params.claudePath, [claudeProjectsRoot()], "claudePath");
        args.push("--claude-path", params.claudePath.trim());
      }
      if (params.piPath?.trim()) {
        assertSafeOverridePath(params.piPath, [piSessionsRoot()], "piPath");
        args.push("--pi-path", params.piPath.trim());
      }

      try {
        const { output, pythonCommand } = await runCmanSearchAll(args, signal);
        return {
          content: [{ type: "text", text: output }],
          details: {
            source: "cman",
            command: [pythonCommand, "scripts/search_all.py", ...args],
          },
        };
      } catch (error) {
        return {
          isError: true,
          content: [{ type: "text", text: `cman_search_all failed: ${error.message}` }],
          details: {
            source: "cman",
            command: ["<python>", "scripts/search_all.py", ...args],
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
        const { output } = await runCmanPiSessions(commandArgs, ctx.signal);
        ctx.ui.notify(output, "info");
      } catch (error) {
        ctx.ui.notify(`cman-pi failed: ${error.message}`, "error");
      }
    },
  });
}
