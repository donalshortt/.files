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

vim.keymap.set('n', 'se', vim.diagnostic.open_float)
vim.keymap.set('n', 'ne', vim.diagnostic.goto_prev)
vim.keymap.set('n', 'pe', vim.diagnostic.goto_next)

vim.api.nvim_create_autocmd('LspAttach', {
	group = vim.api.nvim_create_augroup('UserLspConfig', {}),
	callback = function(ev)
		-- Enable completion triggered by <c-x><c-o>
		vim.bo[ev.buf].omnifunc = 'v:lua.vim.lsp.omnifunc'
	end,
})
