# NFT as collateral

This project is part of the Folks Finance bounty challenge, presented at the Algorand summer school. The challenge is to create a p2p lending-borrowing protocol, in which a user can add an NFT as collateral and ask for any ASA, or even ALGOs. Any other user can accept that loan and send the funds to the borrower. Finally, after some duration has passed, if the borrower has not repayed the loan, lender can liquidate it by taking the collateral NFT.


###  Extra Features:
- Possible lenders can make a proposal to increase the interest of a loan. For example, if a requested loan has 1.00% interest, but you would be interested in accepting it for 2.00%, you can make a proposal and owner can either accept it or decline it.
- Works with ALGOs too and not only with ASAs.
- The tests file contains some utilities used to fetch available loans etc, wrappers for all the contract's functions and tests for most of the functionalities.