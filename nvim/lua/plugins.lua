local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
if not vim.loop.fs_stat(lazypath) then
  vim.fn.system({
    "git",
    "clone",
    "--filter=blob:none",
    "https://github.com/folke/lazy.nvim.git",
    "--branch=stable", -- latest stable release
    lazypath,
  })
end
vim.opt.rtp:prepend(lazypath)

local plugins = {
	-- theme
	'EdenEast/nightfox.nvim',

	-- filetree explorer
	'nvim-tree/nvim-tree.lua',

	-- icons for various plugins
	'nvim-tree/nvim-web-devicons',

	-- pretty bottom statusline
	'nvim-lualine/lualine.nvim',

	-- pretty tabs
	'romgrk/barbar.nvim',

	-- makes ASTs for source files
	'nvim-treesitter/nvim-treesitter',

	-- some sort of utility lib for nvim
	'nvim-lua/plenary.nvim',

	-- find files
	'nvim-telescope/telescope.nvim',

	-- git ui
	'kdheepak/lazygit.nvim',

	-- allow sudo writing
	'lambdalisue/suda.vim',

	-- lsp stuff
		'hrsh7th/nvim-cmp',
		'hrsh7th/cmp-nvim-lsp',
		'L3MON4D3/LuaSnip',
		'saadparwaiz1/cmp_luasnip',
		'rafamadriz/friendly-snippets',
		{
			'williamboman/mason.nvim',
			'williamboman/mason-lspconfig.nvim',
			'neovim/nvim-lspconfig'
		},

		-- handles linters and formatters
		'jose-elias-alvarez/null-ls.nvim',

	'github/copilot.vim',

	-- autocloses things
	'cohama/lexima.vim',

	-- lsp enchancer plugin; floating panes for goto definitions, code actions, etc.
	{"glepnir/lspsaga.nvim", event = "LspAttach"},

	-- helper for shortcuts
	'liuchengxu/vim-which-key',
}

local opts = {}

require("lazy").setup(plugins, opts)
