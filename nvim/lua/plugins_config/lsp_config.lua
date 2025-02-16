require('mason').setup()
require('mason-lspconfig').setup {
	ensure_installed = {
		'clangd',
		'lua_ls',
		'bashls',
		'pyright',
		'ts_ls',
		'eslint',
		'volar'
	}
}

local capabilities = require('cmp_nvim_lsp').default_capabilities(vim.lsp.protocol.make_client_capabilities())
local lspconfig = require('lspconfig')

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
	capabilities = capabilities,
}

lspconfig.ts_ls.setup {
	capabilities = capabilities,
}

lspconfig.eslint.setup {
	capabilities = capabilities,
}

lspconfig.volar.setup {
	capabilities = capabilities,
}

lspconfig.julials.setup {
	capabilities = capabilities,
}
