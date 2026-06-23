require("leetcode").setup({
	---@type string
	arg = "leetcode.nvim",

	---@type lc.lang
	lang = "typescript",

	cn = { -- leetcode.cn
		enabled = false, ---@type boolean
		translator = true, ---@type boolean
		translate_problems = true, ---@type boolean
	},

	---@type lc.storage
	storage = {
		home = vim.fn.stdpath("data") .. "/leetcode",
		cache = vim.fn.stdpath("cache") .. "/leetcode",
	},

	---@type table<string, boolean>
	plugins = {
		non_standalone = false,
	},

	---@type boolean
	logging = true,
	injector = {}, ---@type table<lc.lang, lc.inject>
	cache = {
		update_interval = 60 * 60 * 24 * 7, ---@type integer 7 days
	},

	console = {
		open_on_runcode = true, ---@type boolean
		dir = "row", ---@type lc.direction
		size = { ---@type lc.size
			width = "90%",
			height = "75%",
		},
		result = {
			size = "60%", ---@type lc.size
		},
		testcase = {
			virt_text = true, ---@type boolean
			size = "40%", ---@type lc.size
		},
	},

	description = {
		position = "left", ---@type lc.position
		width = "40%", ---@type lc.size
		show_stats = true, ---@type boolean
	},

	hooks = {
		---@type fun()[]
		["enter"] = {},

		---@type fun(question: lc.ui.Question)[]
		["question_enter"] = {
			function()
				vim.schedule(function()
					local buf = vim.api.nvim_get_current_buf()

					if vim.bo[buf].filetype ~= "rust" then
						return
					end

					local file = vim.api.nvim_buf_get_name(buf)

					if file == "" then
						return
					end

					local dir = vim.fn.fnamemodify(file, ":h")
					local filename = vim.fn.fnamemodify(file, ":t")
					local cargo_toml = dir .. "/Cargo.toml"

					vim.fn.writefile({
						"[package]",
						'name = "leetcode-local"',
						'version = "0.1.0"',
						'edition = "2024"',
						"",
						"[lib]",
						('path = "%s"'):format(filename),
						"",
					}, cargo_toml)

					vim.cmd("silent! RustLsp restart")
				end)
			end,
		},

		---@type fun()[]
		["leave"] = {},
	},

	keys = {
		toggle = { "q" }, ---@type string|string[]
		confirm = { "<CR>" }, ---@type string|string[]

		reset_testcases = "r", ---@type string
		use_testcase = "U", ---@type string
		focus_testcases = "H", ---@type string
		focus_result = "L", ---@type string
	},

	---@type lc.highlights
	theme = {},

	---@type boolean
	image_support = false,
})
