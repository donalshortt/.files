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
-- local lspconfig = require('lspconfig')

vim.lsp.config("clangd", {
	capabilities = capabilities,
	cmd = {
		"clangd",
		"--offset-encoding=utf-16",
	},
})
vim.lsp.enable({"clangd"})

vim.lsp.config("lua_ls", {
	capabilities = capabilities,
	settings = {
		Lua = {
			diagnostics = {
				globals = {'vim'},
			}
		}
	}
})
vim.lsp.enable({"lua_ls"})

vim.lsp.config("bashls", {
	capabilities = capabilities,
})
vim.lsp.enable({"bashls"})

vim.lsp.config("pyright", {
	capabilities = capabilities,
})
vim.lsp.enable({"pyright"})

vim.lsp.config("ts_ls", {
	capabilities = capabilities,
})
vim.lsp.enable({"ts_ls"})

vim.lsp.config("eslint", {
	capabilities = capabilities,
})
vim.lsp.enable({"eslint"})

vim.lsp.config("julials", {
	capabilities = capabilities,
})
vim.lsp.enable({"julials"})

vim.lsp.config("phpactor", {
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
})
vim.lsp.enable({"phpactor"})

vim.api.nvim_create_autocmd("BufWritePre", {
  pattern = "*.rs",
  callback = function()
    vim.lsp.buf.format({ async = false })
  end,
})
