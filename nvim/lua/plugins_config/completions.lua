local cmp = require("cmp")
local lspkind = require('lspkind')

require("luasnip.loaders.from_vscode").lazy_load()

cmp.setup({
	mapping = cmp.mapping.preset.insert({
		['<Tab>'] = cmp.mapping.select_next_item(),
		['<S-Tab>'] = cmp.mapping.select_prev_item(),
		['<C-b>'] = cmp.mapping.scroll_docs(-4),
		['<C-f>'] = cmp.mapping.scroll_docs(4),
		['<C-o>'] = cmp.mapping.complete(),
		['<C-e>'] = cmp.mapping.abort(),
		['<CR>'] = cmp.mapping.confirm({ select = false }),
	}),
	snippet = {
		expand = function(args)
			require('luasnip').lsp_expand(args.body)
		end,
	},
	sources = cmp.config.sources({
		{ name = 'nvim_lsp' },
		{ name = 'luasnip' },
		{ name = 'buffer' },
		{ name = 'copilot' },
	}),
	formatting = {
		format = lspkind.cmp_format({
			mode = 'symbol_text', -- show only symbol annotations
			maxwidth = 50, -- prevent the popup from showing more than provided characters (e.g 50 will not show more than 50 characters)
			ellipsis_char = '...', -- when popup menu exceed maxwidth, the truncated part would show ellipsis_char instead (must define maxwidth first)
			symbol_map = { Copilot = "" }
		  
		  -- The function below will be called before any actual modifications from lspkind
		  -- so that you can provide more controls on popup customization. (See [#30](https://github.com/onsails/lspkind-nvim/pull/30))
		  --before = function (entry, vim_item)
			--...
			--return vim_item
		  --end
		})
	}
})

vim.api.nvim_set_hl(0, "CmpItemKindCopilot", {fg ="#6CC644"})

--[[
symbol_map = {
Text = "󰉿",
Method = "󰆧",
Function = "󰊕",
Constructor = "",
Field = "󰜢",
Variable = "󰀫",
Class = "󰠱",
Interface = "",
Module = "",
Property = "󰜢",
Unit = "󰑭",
Value = "󰎠",
Enum = "",
Keyword = "󰌋",
Snippet = "",
Color = "󰏘",
File = "󰈙",
Reference = "󰈇",
Folder = "󰉋",
EnumMember = "",
Constant = "󰏿",
Struct = "󰙅",
Event = "",
Operator = "󰆕",
TypeParameter = "",
},]]--

