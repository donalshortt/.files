require('mason').setup()
require('mason-lspconfig').setup {
	ensure_installed = {
		'rust_analyzer',
		'clangd',
		'lua_ls',
		'bashls',
	}
}

local capabilities = require('cmp_nvim_lsp').default_capabilities(vim.lsp.protocol.make_client_capabilities())
local lspconfig = require('lspconfig')

lspconfig.rust_analyzer.setup {
	capabilities = capabilities,
}

lspconfig.clangd.setup {
	capabilities = capabilities,
	cmd = {
		"clangd",
		"--offset-encoding=utf-16",
	},
}

lspconfig.lua_ls.setup {
	capabilities = capabilities,
	settings = {
		Lua = {
			diagnostics = {
				globals = {'vim'},
			}
		}
	}
}

lspconfig.bashls.setup {
	capabilities = capabilities,
}

lspconfig.pyright.setup {
	capabilties = capabilities,
}
