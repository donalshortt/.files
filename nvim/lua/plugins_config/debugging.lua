local dap = require("dap")

dap.adapters.gdb = {
  type = "executable",
  command = "rust-gdb",
  args = { "--interpreter=dap", "--eval-command", "set print pretty on", "-q" }
}

dap.configurations.rust = {
	{
		name = "Launch",
		type = "gdb",
		request = "launch",
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
require("dapui").setup(opts)

local dapui = require("dapui")

dap.listeners.before.attach.dapui_config = function()
	dapui.open()
end
dap.listeners.before.launch.dapui_config = function()
	dapui.open()
end
dap.listeners.before.event_terminated.dapui_config = function()
	dapui.close()
end
dap.listeners.before.event_exited.dapui_config = function()
	dapui.close()
end
