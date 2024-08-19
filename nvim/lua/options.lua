vim.opt.tabstop 		= 4
vim.opt.shiftwidth 		= 4
vim.opt.number 			= true
vim.opt.relativenumber 	= true
vim.opt.cursorline 		= true
vim.opt.incsearch       = true
vim.opt.termguicolors 	= true
vim.opt.clipboard 		= 'unnamedplus'
vim.opt.swapfile 		= false
vim.opt.scrolloff 		= 999

--- Make comments italic
vim.api.nvim_set_hl(0, 'Comment', { italic = true })
