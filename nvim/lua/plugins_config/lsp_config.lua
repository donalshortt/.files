require('mason').setup()
require('mason-lspconfig').setup {
	ensure_installed = { 'rust_analyzer', 'clangd', 'lua_ls'}
}

local capabilities = require('cmp_nvim_lsp').default_capabilities(vim.lsp.protocol.make_client_capabilities())

require('lspconfig').rust_analyzer.setup {
	capabilities = capabilities,
}

require('lspconfig').clangd.setup {
	capabilities = capabilities,
}

require('lspconfig').lua_ls.setup {
	capabilities = capabilities,
	settings = {
		Lua = {
			diagnostics = {
				globals = {'vim'},
			}
		}
	}
}
