from pyteal import *
from beaker import *
from helpers.checks import *
from helpers.inners import *

class loanStruct(abi.NamedTuple):
    collateral_id: abi.Field[abi.Uint64]
    borrowing_id: abi.Field[abi.Uint64]
    amount: abi.Field[abi.Uint64]
    interest: abi.Field[abi.Uint64]
    duration: abi.Field[abi.Uint64]
    start: abi.Field[abi.Uint64]
    proposed_interest: abi.Field[abi.Uint64]
    proposer: abi.Field[abi.Address]
    owner: abi.Field[abi.Address]
    lender: abi.Field[abi.Address]

class State:
    loan_counter = GlobalStateValue(
        stack_type=TealType.uint64,
        default=Int(0),
        descr="Loan id tracker",
    )


app = (Application("NFTasCollateral", state=State).apply(unconditional_create_approval, initialize_global_state=True))


@app.external
def opt_into_nft(asset: abi.Asset) -> Expr:
        return send_opt_in_transaction(asset.asset_id())

# Borrower

# Supports Both asa and native algos. Use borrowing_id 0 for ALGO.
@app.external
def request_loan(borrowing_id: abi.Uint64, amount_: abi.Uint64, duration_: abi.Uint64, interest_: abi.Uint64, axfer: abi.AssetTransferTransaction, paytx: abi.PaymentTransaction) -> Expr:
    return Seq(
        # loanStruct size = 112
        # key size = 8
        # MBR = 2500 + 400 * 120
        Assert(axfer.get().asset_receiver() == Global.current_application_address()),
        Assert(axfer.get().asset_amount() == Int(1)),
        Assert(axfer.get().sender() ==Txn.sender()),
        
        Assert(paytx.get().amount() == Int(66500)),
        Assert(paytx.get().receiver() == Global.current_application_address()),
        Assert(paytx.get().sender() == Txn.sender()),
        
        app.state.loan_counter.set(app.state.loan_counter + Int(1)),
        (collateralId := abi.Uint64()).set(axfer.get().xfer_asset()),
        (borrowingId := abi.Uint64()).set(borrowing_id),
        (amount := abi.Uint64()).set(amount_),
        (interest := abi.Uint64()).set(interest_),
        (duration := abi.Uint64()).set(duration_),
        (start := abi.Uint64()).set(Int(0)),
        (proposedInterest := abi.Uint64()).set(Int(0)),
        (owner := abi.Address()).set(Txn.sender()),
        (lender := abi.Address()).set(Global.zero_address()),
        (proposer := abi.Address()).set(Global.zero_address()),
        (ls := loanStruct()).set(collateralId, borrowingId, amount, interest, duration, start, proposedInterest,proposer, owner, lender),
        App.box_put(Itob(app.state.loan_counter),ls.encode()),
        
    )


@app.external
def delete_request(loan_id: abi.Uint64) -> Expr:
    return Seq(
        contents := App.box_get(Itob(loan_id.get())),
        Assert(contents.hasValue()),        
        (ls := loanStruct()).decode(contents.value()),
        
        ls.owner.store_into(owner := abi.Address()),
        Assert(owner.get() == Txn.sender()),
        
        ls.lender.store_into(lender := abi.Address()),
        Assert(lender.get() == Global.zero_address()),
        
        ls.collateral_id.store_into(collateral_id := abi.Uint64()),
        
        send_asset_transfer_transaction(collateral_id.get(), Txn.sender(), Int(1)),
        Assert(App.box_delete(Itob(loan_id.get()))),
        # Transfer the Box's mbr to the user.
        pay(owner.get(), Int(66500)),
    )


@app.external
def repay_loan(loan_id: abi.Uint64, axfer: abi.AssetTransferTransaction) -> Expr:
        return Seq(
            contents := App.box_get(Itob(loan_id.get())),
            Assert(contents.hasValue()),        
            (ls := loanStruct()).decode(contents.value()),
            # Only owner can repay loan
            ls.owner.store_into(owner := abi.Address()),
            Assert(owner.get() == Txn.sender()),
            
            ls.lender.store_into(lender := abi.Address()),
            Assert(lender.get() != Global.zero_address()),
            
            ls.collateral_id.store_into(collateral_id := abi.Uint64()),
            ls.borrowing_id.store_into(borrowing_id := abi.Uint64()),
            ls.amount.store_into(amount := abi.Uint64()),
            ls.start.store_into(start := abi.Uint64()),
            ls.interest.store_into(interest := abi.Uint64()),
            
            # Ensure the xfer was the intended one
            Assert(axfer.get().xfer_asset() == borrowing_id.get()),
            Assert(axfer.get().asset_receiver() == lender.get()),
            Assert(axfer.get().sender() == owner.get()),
            # YInterest is non compound and annual.
            # Loss of precision in yearsPassed is wanted.
            Assert(axfer.get().asset_amount() == (amount.get()*(((Global.latest_timestamp() - start.get())/Int(31556926) * interest.get()) + Int(100_00))/ Int(10000))),
            # Transfer the nft back to borrower 
            send_asset_transfer_transaction(collateral_id.get(), owner.get(), Int(1)),
            # Delete box
            Assert(App.box_delete(Itob(loan_id.get()))),
            pay(owner.get(), Int(66500)),
    )


@app.external
def repay_native_loan(loan_id: abi.Uint64, paytx: abi.PaymentTransaction) -> Expr:
        return Seq(
            contents := App.box_get(Itob(loan_id.get())),
            Assert(contents.hasValue()),        
            (ls := loanStruct()).decode(contents.value()),
            # Only owner can repay loan
            ls.owner.store_into(owner := abi.Address()),
            Assert(owner.get() == Txn.sender()),
            
            ls.lender.store_into(lender := abi.Address()),
            Assert(lender.get() != Global.zero_address()),
            
            ls.collateral_id.store_into(collateral_id := abi.Uint64()),
            ls.borrowing_id.store_into(borrowing_id := abi.Uint64()),
            ls.amount.store_into(amount := abi.Uint64()),
            ls.start.store_into(start := abi.Uint64()),
            ls.interest.store_into(interest := abi.Uint64()),
            
            # Ensure the xfer was the intended one
            Assert(borrowing_id.get() == Int(0)),
            Assert(paytx.get().sender() == owner.get()),
            Assert(paytx.get().receiver() == lender.get()),
            # Interest is non compound and annual.
            # Loss of precision in yearsPassed is wanted.
            Assert(paytx.get().amount() == (amount.get()*(((Global.latest_timestamp() - start.get())/Int(31556926) * interest.get()) + Int(100_00))/ Int(10000))),
            # Transfer the nft back to borrower 
            send_asset_transfer_transaction(collateral_id.get(), owner.get(), Int(1)),
            # Delete box
            Assert(App.box_delete(Itob(loan_id.get()))),
            pay(owner.get(), Int(66500)),
        )


# Lender
@app.external
def accept_loan(loan_id: abi.Uint64, axfer: abi.AssetTransferTransaction):
        return Seq(
            contents := App.box_get(Itob(loan_id.get())),
            Assert(contents.hasValue()),        
            (ls := loanStruct()).decode(contents.value()),
            
            ls.lender.store_into(lender := abi.Address()),
            Assert(lender.get() == Global.zero_address()),
            ls.owner.store_into(owner := abi.Address()),
            
            ls.borrowing_id.store_into(borrowing_id := abi.Uint64()),
            ls.amount.store_into(amount := abi.Uint64()),
            
            # Ensure the xfer was the intended one
            Assert(axfer.get().xfer_asset() == borrowing_id.get()),
            Assert(axfer.get().asset_amount() == amount.get()),
            Assert(axfer.get().asset_receiver() == owner.get()),
            Assert(axfer.get().sender() == Txn.sender()),
            
            lender.set(axfer.get().sender()),

            # Delete box
            # Assert(App.box_delete(Itob(loan_id.get()))),
            ls.collateral_id.store_into(collateral_id := abi.Uint64()),
            ls.interest.store_into(interest := abi.Uint64()),
            ls.duration.store_into(duration := abi.Uint64()),
            ls.proposer.store_into(proposer := abi.Address()),
            # If there was a proposal, transfer the assets back to proposer
            If(proposer.get() != Global.zero_address(),send_asset_transfer_transaction(borrowing_id.get(), proposer.get(), amount.get())),
            
            (start := abi.Uint64()).set(Global.latest_timestamp()),
            (proposedInterest := abi.Uint64()).set(Int(0)),
            proposer.set(Global.zero_address()),
            
            (new_ls := loanStruct()).set(collateral_id, borrowing_id, amount, interest, duration, start, proposedInterest, proposer, owner, lender),
            App.box_put(Itob(loan_id.get()),new_ls.encode()),
        )

@app.external
def accept_native_loan(loan_id: abi.Uint64, paytx: abi.PaymentTransaction):
        return Seq(
            contents := App.box_get(Itob(loan_id.get())),
            Assert(contents.hasValue()),        
            (ls := loanStruct()).decode(contents.value()),
            
            ls.lender.store_into(lender := abi.Address()),
            Assert(lender.get() == Global.zero_address()),
            ls.owner.store_into(owner := abi.Address()),
            
            ls.borrowing_id.store_into(borrowing_id := abi.Uint64()),
            ls.amount.store_into(amount := abi.Uint64()),
            
            # Ensure the xfer was the intended one
            Assert(borrowing_id.get() == Int(0)),
            Assert(paytx.get().amount() == amount.get()),
            Assert(paytx.get().receiver() == owner.get()),
            Assert(paytx.get().sender() == Txn.sender()),
            
            lender.set(paytx.get().sender()),
            # Update box
            ls.collateral_id.store_into(collateral_id := abi.Uint64()),
            ls.interest.store_into(interest := abi.Uint64()),
            ls.duration.store_into(duration := abi.Uint64()),
            (start := abi.Uint64()).set(Global.latest_timestamp()),
            
            ls.proposer.store_into(proposer := abi.Address()),
            If(proposer.get() != Global.zero_address(),pay(proposer.get(), amount.get())),
            
            (proposedInterest := abi.Uint64()).set(Int(0)),
            proposer.set(Global.zero_address()),
            
            (new_ls := loanStruct()).set(collateral_id, borrowing_id, amount, interest, duration, start, proposedInterest, proposer, owner, lender),
            App.box_put(Itob(loan_id.get()),new_ls.encode()),
        )

@app.external
def liquidate_loan(loan_id: abi.Uint64) -> Expr:
    return Seq(
        contents := App.box_get(Itob(loan_id.get())),
        Assert(contents.hasValue()),        
        (ls := loanStruct()).decode(contents.value()),
        # Only lender can liquidate
        ls.lender.store_into(lender := abi.Address()),
        Assert(lender.get() == Txn.sender()),
        
        ls.start.store_into(start := abi.Uint64()),
        ls.duration.store_into(duration := abi.Uint64()),
        
        Assert(Global.latest_timestamp() - start.get() >= duration.get()),
        
        ls.owner.store_into(owner := abi.Address()),
            
        ls.collateral_id.store_into(collateral_id := abi.Uint64()),
        
        send_asset_transfer_transaction(collateral_id.get(), lender.get(), Int(1)),
        Assert(App.box_delete(Itob(loan_id.get()))),
        pay(owner.get(), Int(66500)),
    )
    
#### Interest Proposals Feature

# Possible lender can propose a new interest and send the funds to the contract.
@app.external
def propose_interest(loan_id: abi.Uint64, proposed_interest: abi.Uint64, axfer: abi.AssetTransferTransaction) -> Expr:
        return Seq(
            contents := App.box_get(Itob(loan_id.get())),
            Assert(contents.hasValue()),        
            (ls := loanStruct()).decode(contents.value()),
            
            # Ensure not accepted yet
            ls.lender.store_into(lender := abi.Address()),
            Assert(lender.get() == Global.zero_address()),
            # Noone else has proposed yet
            ls.proposer.store_into(old_proposer := abi.Address()),
            Assert(old_proposer.get() == Global.zero_address()),
            
            ls.owner.store_into(owner := abi.Address()),
            ls.borrowing_id.store_into(borrowing_id := abi.Uint64()),
            ls.amount.store_into(amount := abi.Uint64()),
            
            # Ensure the xfer was the intended one
            Assert(axfer.get().xfer_asset() == borrowing_id.get()),
            Assert(axfer.get().asset_amount() == amount.get()),
            Assert(axfer.get().asset_receiver() == Global.current_application_address()),
            Assert(axfer.get().sender() == Txn.sender()),
            
            # Delete box
            # Assert(App.box_delete(Itob(loan_id.get()))),
            ls.collateral_id.store_into(collateral_id := abi.Uint64()),
            ls.interest.store_into(interest := abi.Uint64()),
            ls.duration.store_into(duration := abi.Uint64()),

            ls.start.store_into(start := abi.Uint64()),
            (new_proposer := abi.Address()).set(Txn.sender()),
            
            
            (new_ls := loanStruct()).set(collateral_id, borrowing_id, amount, interest, duration, start, proposed_interest, new_proposer, owner, lender),
            App.box_put(Itob(loan_id.get()),new_ls.encode()),
        )
        
@app.external
def propose_native_interest(loan_id: abi.Uint64, proposed_interest: abi.Uint64, paytx: abi.PaymentTransaction) -> Expr:
        return Seq(
            contents := App.box_get(Itob(loan_id.get())),
            Assert(contents.hasValue()),        
            (ls := loanStruct()).decode(contents.value()),
            
            # Ensure not accepted yet
            ls.lender.store_into(lender := abi.Address()),
            Assert(lender.get() == Global.zero_address()),
            # Noone else has proposed yet
            ls.proposer.store_into(old_proposer := abi.Address()),
            Assert(old_proposer.get() == Global.zero_address()),
            ls.borrowing_id.store_into(borrowing_id := abi.Uint64()),
            Assert(borrowing_id.get() == Int(0)),
            
            ls.owner.store_into(owner := abi.Address()),
            ls.amount.store_into(amount := abi.Uint64()),
            
            # Ensure the xfer was the intended one
             Assert(paytx.get().amount() == amount.get()),
            Assert(paytx.get().receiver() == Global.current_application_address()),
            Assert(paytx.get().sender() == Txn.sender()),
            
            # Delete box
            # Assert(App.box_delete(Itob(loan_id.get()))),
            ls.collateral_id.store_into(collateral_id := abi.Uint64()),
            ls.interest.store_into(interest := abi.Uint64()),
            ls.duration.store_into(duration := abi.Uint64()),

            ls.start.store_into(start := abi.Uint64()),
            (new_proposer := abi.Address()).set(Txn.sender()),
            
            
            (new_ls := loanStruct()).set(collateral_id, borrowing_id, amount, interest, duration, start, proposed_interest, new_proposer, owner, lender),
            App.box_put(Itob(loan_id.get()),new_ls.encode()),
        )
        
# Proposer can revoke his proposal and get his funds back
@app.external
def revoke_proposal(loan_id: abi.Uint64) -> Expr:
        return Seq(
            contents := App.box_get(Itob(loan_id.get())),
            Assert(contents.hasValue()),        
            (ls := loanStruct()).decode(contents.value()),
            
            # Ensure not accepted yet
            ls.lender.store_into(lender := abi.Address()),
            Assert(lender.get() == Global.zero_address()),
            # Only proposer or owner can revoke.
            ls.proposer.store_into(prev_proposer := abi.Address()),
            ls.owner.store_into(owner := abi.Address()),
            
            Assert(Or(prev_proposer.get() == Txn.sender(),owner.get() == Txn.sender())),
            ls.borrowing_id.store_into(borrowing_id := abi.Uint64()),
            ls.amount.store_into(amount := abi.Uint64()),

            
            ls.collateral_id.store_into(collateral_id := abi.Uint64()),
            ls.interest.store_into(interest := abi.Uint64()),
            ls.duration.store_into(duration := abi.Uint64()),
                        
            (proposedInterest := abi.Uint64()).set(Int(0)),
            (start := abi.Uint64()).set(Int(0)),
            (proposer := abi.Address()).set(Global.zero_address()),
            
            (new_ls := loanStruct()).set(collateral_id, borrowing_id, amount, interest, duration, start, proposedInterest, proposer, owner, lender),
            App.box_put(Itob(loan_id.get()),new_ls.encode()),
            # Works for both ALGO and asa loans
            If(borrowing_id.get() == Int(0),pay(prev_proposer.get(), amount.get()), send_asset_transfer_transaction(borrowing_id.get(), prev_proposer.get(), amount.get())),
        )

# Borrower can accept a proposal, update interest and get the amount
@app.external
def accept_proposal(loan_id: abi.Uint64) -> Expr:
        return Seq(
            contents := App.box_get(Itob(loan_id.get())),
            Assert(contents.hasValue()),        
            (ls := loanStruct()).decode(contents.value()),
            
            # Ensure not accepted yet
            ls.lender.store_into(lender := abi.Address()),
            Assert(lender.get() == Global.zero_address()),
            # There is a proposer
            ls.proposer.store_into(proposer := abi.Address()),
            Assert(proposer.get() != Global.zero_address()),
            
            (lender := abi.Address()).set(proposer.get()),
            ls.owner.store_into(owner := abi.Address()),
            Assert(owner.get() == Txn.sender()),
            
            ls.borrowing_id.store_into(borrowing_id := abi.Uint64()),
            ls.amount.store_into(amount := abi.Uint64()),
            ls.proposed_interest.store_into(proposed_interest := abi.Uint64()),
            
            ls.collateral_id.store_into(collateral_id := abi.Uint64()),
            ls.duration.store_into(duration := abi.Uint64()),
                        
            (proposedInterest := abi.Uint64()).set(Int(0)),
            (start := abi.Uint64()).set(Global.latest_timestamp()),
            (proposer := abi.Address()).set(Global.zero_address()),
            (interest := abi.Uint64()).set(proposed_interest.get()),
            
            (new_ls := loanStruct()).set(collateral_id, borrowing_id, amount, interest, duration, start, proposedInterest, proposer, owner, lender),
            App.box_put(Itob(loan_id.get()),new_ls.encode()),
            
            If(borrowing_id.get() == Int(0),pay(Txn.sender(), amount.get()), send_asset_transfer_transaction(borrowing_id.get(), Txn.sender(), amount.get())),
        )