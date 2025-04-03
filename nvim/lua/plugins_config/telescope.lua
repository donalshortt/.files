require('telescope').setup{
    defaults = {
      layout_strategy = 'vertical',
      layout_config = { height = 0.95 },
    },
	pickers = {
		find_files = {
			find_command = { "rg", "--files", "--no-ignore", "--hidden", "--glob", "!**/.git/*" }
		},
	}
}
