set nocompatible

call plug#begin(stdpath('data') . '/plugged')
 
	Plug 'frazrepo/vim-rainbow'
	Plug 'sheerun/vim-polyglot'
	Plug 'ms-jpq/chadtree', {'branch': 'chad', 'do': 'python3 -m chadtree deps'}
	Plug 'dstein64/nvim-scrollview', { 'branch': 'main' }
	Plug 'bfrg/vim-cpp-modern'
	Plug 'neoclide/coc.nvim', {'branch': 'release'}
	Plug 'EdenEast/nightfox.nvim'
	Plug 'kyazdani42/nvim-web-devicons'
	Plug 'nvim-treesitter/nvim-treesitter', {'do': ':TSUpdate'}
	Plug 'nvim-lua/plenary.nvim'
	Plug 'nvim-telescope/telescope.nvim'
	Plug 'itchyny/lightline.vim'
	Plug 'lambdalisue/suda.vim'
	Plug 'fladson/vim-kitty'
	Plug 'shirk/vim-gas'
	Plug 'habamax/vim-godot'
	Plug 'clktmr/vim-gdscript3'
	Plug 'kdheepak/lazygit.nvim'
	Plug 's1n7ax/nvim-terminal'
	Plug 'wakatime/vim-wakatime'
	Plug 'cohama/lexima.vim'
	Plug 'alvan/vim-closetag'
	Plug 'chrisbra/unicode.vim'
	Plug 'itchyny/vim-gitbranch'

call plug#end()

" custom keybinds
source ~/.files/nvim_config/keybinds.vim

" coc 
source ~/.files/nvim_config/coc.vim
" nightfox 
source ~/.files/nvim_config/nightfox.lua
" telescope 
source ~/.files/nvim_config/telescope.vim
" lightline 
source ~/.files/nvim_config/lightline.vim
" lazygit 
source ~/.files/nvim_config/lazygit.vim
" nvim-terminal
source ~/.files/nvim_config/terminal.lua
" chadtree
source ~/.files/nvim_config/chadtree.vim
" vim-godot
source ~/.files/nvim_config/vim_godot.vim
" cpp-modern
source ~/.files/nvim_config/cpp_modern.vim
" rainbow
source ~/.files/nvim_config/rainbow.vim
" closetag
source ~/.files/nvim_config/closetag.vim


set tabstop=4
set shiftwidth=4
set noexpandtab
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
set statusline^=%{coc#status()}%{get(b:,'coc_current_function','')}
set cursorline
set clipboard+=unnamedplus
set noshowmode
set ft=asm


" sets background to transparent
autocmd vimenter * hi Normal guibg=NONE ctermbg=NONE
