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
	'EdenEast/nightfox.nvim',
	'nvim-tree/nvim-tree.lua',
	'nvim-tree/nvim-web-devicons',
	'nvim-lualine/lualine.nvim',

	'nvim-treesitter/nvim-treesitter',
	'nvim-lua/plenary.nvim',
	'nvim-telescope/telescope.nvim',

	'kdheepak/lazygit.nvim',
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

	'github/copilot.vim',

	'cohama/lexima.vim',
}

local opts = {}

require("lazy").setup(plugins, opts)
