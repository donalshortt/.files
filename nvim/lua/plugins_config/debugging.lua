local dap = require("dap")

dap.adapters.gdb = {
  type = "executable",
  command = "rust-gdb",
  args = { "--interpreter=dap",
    "--eval-command=set print pretty on",
    "--eval-command=set debuginfod enabled on",
  "-q"
  }
}
local cwd        = vim.fn.getcwd()
local deps_dir   = cwd .. "/target/debug/deps"

-- get the sysroot, e.g. /home/user/.rustup/toolchains/stable-x86_64-unknown-linux-gnu
local sysroot    = vim.fn.trim(vim.fn.system("rustc --print sysroot"))
-- get the host triple, e.g. x86_64-unknown-linux-gnu
local host_triple = vim.fn.trim(vim.fn.system("rustc -Vv | awk '/host:/ {print $2}'"))
local stdlib_dir = sysroot .. "/lib/rustlib/" .. host_triple .. "/lib"

-- preserve any existing LD_LIBRARY_PATH
local old_ld = os.getenv("LD_LIBRARY_PATH") or ""

-- build a colon-separated path
local ldpath = table.concat(
  { deps_dir, stdlib_dir, old_ld ~= "" and old_ld or nil },
  ":"
)

dap.configurations.rust = {
	{
		name = "Launch",
		type = "gdb",
		request = "launch",
		env     = {
			CARGO_MANIFEST_DIR = cwd,
			LD_LIBRARY_PATH    = ldpath,
			DISPLAY            = os.getenv("DISPLAY"),
			WAYLAND_DISPLAY    = os.getenv("WAYLAND_DISPLAY"),
			XDG_RUNTIME_DIR    = os.getenv("XDG_RUNTIME_DIR"),
		},
		program = function()
			-- Ensure the project is built before launching
			os.execute('cargo build')

			-- Automatically infer the executable from Cargo.toml
			local handle = io.popen('cargo metadata --no-deps --format-version=1 | jq -r ".packages[0].targets[0].name"')
			local target_name = handle:read("*a"):gsub("%s+", "")
			handle:close()

			local executable = vim.fn.getcwd() .. '/target/debug/' .. target_name
			return executable
		end,
		cwd = "${workspaceFolder}",
		stopAtBeginningOfMainSubprogram = false,
	},
	{
		name = "Select and attach to process",
		type = "gdb",
		request = "attach",
		env     = {
			CARGO_MANIFEST_DIR = cwd,
			LD_LIBRARY_PATH    = ldpath,
			DISPLAY            = os.getenv("DISPLAY"),
			WAYLAND_DISPLAY    = os.getenv("WAYLAND_DISPLAY"),
			XDG_RUNTIME_DIR    = os.getenv("XDG_RUNTIME_DIR"),
		},
		program = function()
			-- Ensure the project is built
			os.execute('cargo build')

			-- Automatically infer the executable
			local handle = io.popen('cargo metadata --no-deps --format-version=1 | jq -r ".packages[0].targets[0].name"')
			local target_name = handle:read("*a"):gsub("%s+", "")
			handle:close()

			local executable = vim.fn.getcwd() .. '/target/debug/' .. target_name
			return executable
		end,
		pid = function()
			local name = vim.fn.input('Executable name (filter): ')
			return require("dap.utils").pick_process({ filter = name })
		end,
		cwd = '${workspaceFolder}'
	},
	{
		name = 'Attach to gdbserver :1234',
		type = 'gdb',
		request = 'attach',
		env     = {
			CARGO_MANIFEST_DIR = cwd,
			LD_LIBRARY_PATH    = ldpath,
			DISPLAY            = os.getenv("DISPLAY"),
			WAYLAND_DISPLAY    = os.getenv("WAYLAND_DISPLAY"),
			XDG_RUNTIME_DIR    = os.getenv("XDG_RUNTIME_DIR"),
		},
		target = 'localhost:1234',
		program = function()
			-- Ensure the project is built
			os.execute('cargo build')

			-- Automatically infer the executable
			local handle = io.popen('cargo metadata --no-deps --format-version=1 | jq -r ".packages[0].targets[0].name"')
			local target_name = handle:read("*a"):gsub("%s+", "")
			handle:close()

			local executable = vim.fn.getcwd() .. '/target/debug/' .. target_name
			return executable
		end,
		cwd = '${workspaceFolder}'
	},
}

local opts = {
	layouts = {
		{
			elements = {
				{ id = "breakpoints", size = 1 },
			},
			position = "top",
			size = 3,
		},
		{
			elements = {
				{ id = "watches", size = 1 },
			},
			position = "top",
			size = 5,
		},
		{
			elements = {
				{ id = "scopes", size = 1 },
			},
			position = "top",
			size = 10,
		},
		{
			elements = {
				{ id = "console", size = 1 },
			},
			position = "bottom",
			size = 5,
		},
		{
			elements = {
				{ id = "repl", size = 1 },
			},
			position = "bottom",
			size = 9,
		},
	},
}

local dapui = require("dapui")
dapui.setup(opts)

dap.listeners.after.event_initialized["dapui"] = function()
  dapui.open()
end
dap.listeners.before.event_terminated["dapui"] = function()
  dapui.close()
end
dap.listeners.before.event_exited["dapui"] = function()
  dapui.close()
end
