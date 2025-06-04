require('mason').setup()
require('mason-lspconfig').setup {
	ensure_installed = {
		'clangd',
		'lua_ls',
		'bashls',
		'pyright',
		'ts_ls',
		'eslint',
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

lspconfig.julials.setup {
	capabilities = capabilities,
}

require("lspconfig").phpactor.setup {
  root_dir = function(_)
    return vim.loop.cwd()
  end,
  init_options = { 
    ["language_server.diagnostics_on_update"] = false,
    ["language_server.diagnostics_on_open"] = false,
    ["language_server.diagnostics_on_save"] = false,
    ["language_server_phpstan.enabled"] = false,
    ["language_server_psalm.enabled"] = false,
  }
}
