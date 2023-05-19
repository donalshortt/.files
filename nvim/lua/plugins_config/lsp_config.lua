require('mason').setup()
require('mason-lspconfig').setup {
	ensure_installed = { 'rust_analyzer', 'clangd', 'lua_ls', 'bashls' }
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

		-- Buffer local mappings.
		-- See `:help vim.lsp.*` for documentation on any of the below functions
		local opts = { buffer = ev.buf }
		vim.keymap.set('n', 'gD', vim.lsp.buf.declaration, opts)
		vim.keymap.set('n', 'gd', vim.lsp.buf.definition, opts)
		vim.keymap.set('n', 'gi', vim.lsp.buf.implementation, opts)
		vim.keymap.set('n', 'rn', vim.lsp.buf.rename, opts)
		vim.keymap.set('n', 'gr', vim.lsp.buf.references, opts)
	end,
})
