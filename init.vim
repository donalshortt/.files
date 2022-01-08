set nocompatible

call plug#begin(stdpath('data') . '/plugged')
 
    Plug 'frazrepo/vim-rainbow'
    Plug 'sheerun/vim-polyglot'
    Plug 'preservim/nerdtree'
    Plug 'dstein64/nvim-scrollview', { 'branch': 'main' }
    Plug 'bfrg/vim-cpp-modern'
    Plug 'neoclide/coc.nvim', {'branch': 'release'}
    Plug 'Xuyuanp/nerdtree-git-plugin'
    Plug 'ryanoasis/vim-devicons'
    Plug 'EdenEast/nightfox.nvim'
    Plug 'kyazdani42/nvim-web-devicons'
    Plug 'nvim-treesitter/nvim-treesitter', {'do': ':TSUpdate'}
    Plug 'nvim-lua/plenary.nvim'
    Plug 'nvim-telescope/telescope.nvim'
    Plug 'itchyny/lightline.vim'

call plug#end()

" jump to beginning/end of line while in insert
inoremap <C-e> <C-o>$
inoremap <C-a> <C-o>0

" COC config
source ~/.files/nvim_config/coc.vim
" Nightfox config
source ~/.files/nvim_config/nightfox.lua
" Telescope config
source ~/.files/nvim_config/telescope.vim
" Lightline config
source ~/.files/nvim_config/lightline.vim

" set termguicolors
set tabstop=4
set shiftwidth=4
set expandtab
set number
set relativenumber
set autoread
set hlsearch
set hidden
set nobackup
set nowritebackup
set updatetime=300
set shortmess+=c
set signcolumn=number
" Add (Neo)Vim's native statusline support.
" NOTE: Please see `:h coc-status` for integrations with external plugins that
" provide custom statusline: lightline.vim, vim-airline.
set statusline^=%{coc#status()}%{get(b:,'coc_current_function','')}
set cursorline
set clipboard+=unnamedplus
set noshowmode

syntax on
colo nightfox
autocmd vimenter * hi Normal guibg=NONE ctermbg=NONE

let g:rainbow_active = 1

" Enable highlighting of C++11 attributes
let g:cpp_attributes_highlight = 1

" Highlight struct/class member variables (affects both C and C++ files)
let g:cpp_member_highlight = 1

" open auto, start cursor in file, close if last window open
au VimEnter NERD_tree_1 enew | execute 'NERDTree '.argv()[0] 
" autocmd VimEnter * wincmd p
autocmd bufenter * if (winnr("$") == 1 && exists("b:NERDTree") && b:NERDTree.isTabTree()) | q | endif

