require('telescope').setup {
	pickers = {
		find_files = {
			find_command = { "rg", "--files", "--no-ignore", "--hidden", "--glob", "!**/.git/*" }
		},
	}
}
