# BierKoning

## Beer management system for student houses
Some student houses love to drink beer (or other beverages) together. This software makes it easier to track the purchase and availability of it.

## Decisions
Each student house has their own set of rules for beer distribution, here is mine
1. Only one person buys and manage the beers, De Bier Koning
2. The house cash covers rotation of beer and deposits; it starts at EUR 180.00 (asked on first run)
3. Every person pays for the beers that they drink
4. A normal deposit is not a cost; it comes back when the crate is returned
5. Missing beers and missing deposit are divided among everyone that drank from the crate
6. Counting of beers is done outside of the system
7. Inputs of beer consumption and missing deposit is done right before the crate is returned
8. Cash, deposits, beer stock and outstanding debts always add up to the opening cash

## How to use
Currently, it is a TUI only application. You need [uv](https://docs.astral.sh/uv/getting-started/installation/) and git.
1. Run ```uv tool install git+https://github.com/GregoryJaperson/BierKoning```
2. Run ```uv tool update-shell``` once, then open a new terminal (puts `bierkoning` on your PATH)
3. Type ```bierkoning``` from any folder

Update later with ```uv tool upgrade bierkoning```.

Your data is kept per user, outside the install:
- Linux: `~/.local/share/bierkoning/beer.db`
- macOS: `~/Library/Application Support/BierKoning/beer.db`
- Windows: `%APPDATA%\BierKoning\beer.db`

## Development
1. Clone this repository and run ```uv sync```
2. Run ```uv tool install --editable .``` so `bierkoning` runs your working copy

## Tests
```uv run python -m unittest discover -v```



