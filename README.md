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
Currently, it is a TUI only application, here is a step-by-step tutorial on how to use it:
1. Clone this repository
2. Run ```uv sync``` to create the environment and install dependencies
3. Run ```uv run python main.py``` to run the main menu (it creates/upgrades the sqlite database on start; ```uv run python migrate.py``` does only that)

## Tests
```uv run python -m unittest discover -v```



