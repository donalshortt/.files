require('mason').setup()
require('mason-lspconfig').setup {
	ensure_installed = { 'rust_analyzer', 'clangd', 'lua_ls'}
}

local lspconfig = require('lspconfig')

lspconfig.rust_analyzer.setup {}
lspconfig.clangd.setup {}
lspconfig.lua_ls.setup {}

