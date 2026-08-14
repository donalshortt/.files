local treesitter = require("nvim-treesitter")

treesitter.setup()

treesitter.install({
    "c",
    "lua",
    "rust",
    "vim",
})

vim.api.nvim_create_autocmd("FileType", {
    pattern = {
        "c",
        "lua",
        "rust",
        "vim",
    },
    callback = function(args)
        vim.treesitter.start(args.buf)
    end,
})
