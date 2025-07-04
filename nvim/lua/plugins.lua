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

	-- icons for various plugins
	'nvim-tree/nvim-web-devicons',

	-- pretty bottom statusline
	'freddiehaddad/feline.nvim',

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
	'onsails/lspkind.nvim',
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
	'nvimtools/none-ls.nvim',

	-- github copilot
	'zbirenbaum/copilot.lua',
	'zbirenbaum/copilot-cmp',

	-- lsp enchancer plugin; floating panes for goto definitions, code actions, etc.
	{"glepnir/lspsaga.nvim", event = "LspAttach"},

	-- shows where edits were made according to git
	'lewis6991/gitsigns.nvim',

	-- markdown previewer
	{
		"iamcco/markdown-preview.nvim",
		cmd = { "MarkdownPreviewToggle", "MarkdownPreview", "MarkdownPreviewStop" },
		build = "cd app && yarn install",
		init = function()
			vim.g.mkdp_filetypes = { "markdown" }
		end,
		ft = { "markdown" },
	},

	-- surround things!
	'tpope/vim-surround',

	-- comment things!
	'tpope/vim-commentary',

	-- ui components library
	'MunifTanjim/nui.nvim',

	-- notification manager
	"rcarriga/nvim-notify",

	-- leetcode
	"kawre/leetcode.nvim",

	-- git plugin 
	'tpope/vim-fugitive',

	-- rustacean (extra rust features)
	{
		'mrcjkb/rustaceanvim',
		version = '^5', -- Recommended
		lazy = false, -- This plugin is already lazy
	},

	-- debugger
	'mfussenegger/nvim-dap',
	'rcarriga/nvim-dap-ui',
	'nvim-neotest/nvim-nio',
	'folke/lazydev.nvim',

	-- tree
	'ms-jpq/chadtree',

	-- autocloses things
	'cohama/lexima.vim',

	-- make text pretty
	'godlygeek/tabular',
}

local opts = {}

require("lazy").setup(plugins, opts)
