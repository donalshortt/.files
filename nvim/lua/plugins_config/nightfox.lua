-- Default options
require('nightfox').setup({
  options = {
    -- Compiled files destination location
    compile_file_suffix = "_compiled", -- Compiled file suffix
    transparent = true,    -- Disable setting background
    terminal_colors = true, -- Set terminal colors (vim.g.terminal_color_*)
    dim_inactive = false,   -- Non focused panes set to alternative background
    styles = {              -- Style to be applied to different syntax groups
      comments = "NONE",
      functions = "NONE",
      keywords = "NONE",
      numbers = "NONE",
      strings = "NONE",
      types = "NONE",
      variables = "NONE",
    },
    inverse = {             -- Inverse highlight for different types
      match_paren = false,
      visual = false,
      search = false,
    },
    modules = {             -- List of various plugins and additional options
      -- ...
    },
  }
})

-- setup must be called before loading
vim.cmd("colorscheme nightfox")
