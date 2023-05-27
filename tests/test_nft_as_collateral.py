from tests import *
from tests.helpers import *
from tests.fixtures import *
from app import *
import base64
from Crypto.Util import number
from math import floor
from time import time

####### Utilities and helpers

def isAccepted(boxContents):
    return not boxContents['value'].endswith("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")

def unpackBox(boxContents):
    contents = base64.b64decode(boxContents['value'])
    ret = []

    for i in range(7):
        ret.append(number.bytes_to_long(contents[i*8: (i+1)*8]))
    for j in range(3):
        ret.append(encoding.encode_address(contents[56 + 32*j:88+32*j]))
    return ret
    
def getLoans(algod_client: AlgodClient, app_id):
    boxes = algod_client.application_boxes(app_id)['boxes']
    return boxes

def getAvailableLoans(algod_client: AlgodClient, app_id, idOnly = False):
    
    boxes = getLoans(algod_client, app_id)
    availableLoans = []
    for box_name in boxes:
        loan = algod_client.application_box_by_name(app_id, base64.b64decode(box_name['name']))
        if not isAccepted(loan):
            if idOnly:
                availableLoans.append(number.bytes_to_long(base64.b64decode(box_name['name'])))
            else:
                availableLoans.append(unpackBox(loan))
    return availableLoans

def formatLoan(loan):
    ret = dict()
    ret['collateral_id'] = loan[0]
    ret['borrowing_id'] = loan[1]
    ret['amount'] = loan[2]
    ret['interest'] = loan[3]
    ret['duration'] = loan[4]
    ret['start'] = loan[5]
    ret['proposed_interest'] = loan[6]
    ret['proposer'] = loan[7]
    ret['borrower'] = loan[8]
    ret['lender'] = loan[9]
    return ret

def formatLoanById(algod_client: AlgodClient, app_id, loan_id):
    loan = unpackBox(algod_client.application_box_by_name(app_id, int(loan_id).to_bytes(8)))
    return formatLoan(loan)
    
def getLoanCounter(client):
    return client.get_global_state()['loan_counter']

def getLoansByUser(algod_client: AlgodClient, app_id, address):
    boxes = getLoans(algod_client, app_id)
    userLoans = []
    for box_name in boxes:
        loan = unpackBox(algod_client.application_box_by_name(app_id, base64.b64decode(box_name['name'])))
        if loan[8] == address or loan[9] == address:
            userLoans.append(number.bytes_to_long(base64.b64decode(box_name['name'])))
    return userLoans


###### Wrappers

def acceptLoan(algod_client: AlgodClient, app_id, loan_id, sender):
    client = ApplicationClient(
        client= algod_client,
        app= app,
        signer= sender.signer,
        app_id= app_id,
    )
    loan = unpackBox(algod_client.application_box_by_name(app_id, int(loan_id).to_bytes(8)))
    collateral_id = loan[0]
    token_id = loan[1]
    amount = loan[2]
    borrower = loan[8]
    proposer = loan[7]
    
    if token_id != 0:
        opt_in_asset(algod_client, sender, collateral_id)
        
        sp = client.get_suggested_params()
        
        
        axfer = TransactionWithSigner(
            txn=transaction.AssetTransferTxn(
                sender=sender.address,
                receiver=borrower,
                index=token_id,
                amt=amount,
                sp=sp,
            ),
            signer=sender.signer,
        )
        
        if proposer != "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==":
            sp.fee = sp.min_fee * 2
        client.call(accept_loan, axfer=axfer, loan_id = loan_id, suggested_params = sp, boxes = [(app_id, int(loan_id).to_bytes(8))], foreign_assets=[token_id], accounts=[proposer], signer = sender.signer, sender = sender.address)
    else:
        sp = client.get_suggested_params()
    
    
        paytx =TransactionWithSigner(
            txn = transaction.PaymentTxn(
                sender=sender.address,
                receiver = borrower,
                amt = amount,
                sp = sp
            ),
            signer = sender.signer
        )
        if proposer != "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==":
            sp.fee = sp.min_fee * 2
        client.call(accept_native_loan, paytx = paytx, loan_id = loan_id, suggested_params = sp, boxes = [(app_id, int(loan_id).to_bytes(8))], signer = sender.signer, sender = sender.address)
   
def deleteRequest(algod_client: AlgodClient,app_id, loan_id, sender):
    client = ApplicationClient(
        client= algod_client,
        app= app,
        signer= sender.signer,
        app_id= app_id,
    )
    loan = unpackBox(algod_client.application_box_by_name(app_id, int(loan_id).to_bytes(8)))
    asset = loan[0]
    sp = client.get_suggested_params()
    sp.fee = sp.min_fee * 2
    client.call(delete_request, loan_id = loan_id, signer = sender.signer, sender =sender.address, suggested_params = sp, boxes = [(app_id, int(loan_id).to_bytes(8))], foreign_assets = [asset])
   
def requestLoan(algod_client: AlgodClient, app_id, nft_id, amount, borrowing_id, duration, interest, sender):
    # get_application_address
    client = ApplicationClient(
        client= algod_client,
        app= app,
        signer= sender.signer,
        app_id= app_id,
    )
    
    client.fund(2000000)
    if borrowing_id != 0:
        opt_in_asset(algod_client, sender, borrowing_id)
    sp = client.get_suggested_params()
    sp.fee = sp.min_fee * 2
    
    
    client.call(opt_into_nft, asset = nft_id, suggested_params=sp)
    
    
    axfer = TransactionWithSigner(
        txn=transaction.AssetTransferTxn(
            sender=sender.address,
            receiver=client.app_addr,
            index=nft_id,
            amt=1,
            sp=sp,
        ),
        signer=sender.signer,
    )

    paytx =TransactionWithSigner(
        txn = transaction.PaymentTxn(
            sender=sender.address,
            receiver = client.app_addr,
            amt = 66500,
            sp = sp
        ),
        signer = sender.signer
    )
    
    client.call(request_loan, paytx = paytx, axfer=axfer, borrowing_id=borrowing_id, amount_ = amount, duration_ = duration, interest_ = interest, suggested_params = client.get_suggested_params(), boxes = [(app_id, int(getLoanCounter(client)+1).to_bytes(8))])
    
def repayLoan(algod_client: AlgodClient, app_id, loan_id, sender):
    client = ApplicationClient(
        client= algod_client,
        app= app,
        signer= sender.signer,
        app_id= app_id,
    )
    loan = formatLoanById(algod_client, app_id, loan_id)
    # Not 100% accurate, as time.time() != latest_timestamp, but enough

    yearsPassed = floor((floor(time()) - loan['start'])/ 31556926)

    payback_amt = floor(loan['amount'] * (loan["interest"] * yearsPassed + 10000) / 10000)
    # Loan that borrowed ASAs
    if loan['borrowing_id'] != 0:
        axfer = TransactionWithSigner(
            txn=transaction.AssetTransferTxn(
                sender=sender.address,
                receiver=loan['lender'],
                index=loan['borrowing_id'],
                amt=payback_amt,
                sp=client.get_suggested_params(),
            ),
            signer=sender.signer,
        )
        sp = client.get_suggested_params()
        sp.fee = sp.min_fee * 3
        client.call(repay_loan,loan_id = loan_id, axfer = axfer, suggested_params =sp , boxes = [(app_id, int(loan_id).to_bytes(8))], foreign_assets=[loan['collateral_id']], accounts=[loan['borrower']])
    # Loan that borrowed algos
    else:
        paytx =TransactionWithSigner(
            txn = transaction.PaymentTxn(
                sender=sender.address,
                receiver = loan['lender'],
                amt = payback_amt,
                sp = client.get_suggested_params()
            ),
            signer = sender.signer
        )
        sp = client.get_suggested_params()
        sp.fee = sp.min_fee * 3
        client.call(repay_native_loan,loan_id = loan_id, paytx=paytx, suggested_params =sp , boxes = [(app_id, int(loan_id).to_bytes(8))], foreign_assets=[loan['collateral_id']], accounts=[loan['borrower']])
    
def liquidateLoan(algod_client: AlgodClient, app_id, loan_id, sender):
    client = ApplicationClient(
        client= algod_client,
        app= app,
        signer= sender.signer,
        app_id= app_id,
    )
    loan = unpackBox(algod_client.application_box_by_name(app_id, int(loan_id).to_bytes(8)))
    nft_id = loan[0]
    owner = loan[8]
    sp = client.get_suggested_params()
    sp.fee = sp.min_fee * 2
    client.call(liquidate_loan,loan_id = loan_id, suggested_params =sp , boxes = [(app_id, int(loan_id).to_bytes(8))], foreign_assets=[nft_id], accounts=[owner])

def proposeInterest(algod_client: AlgodClient, app_id, loan_id, proposal, sender):
    client = ApplicationClient(
        client= algod_client,
        app= app,
        signer= sender.signer,
        app_id= app_id,
    )
    loan = formatLoan(unpackBox(algod_client.application_box_by_name(app_id, int(loan_id).to_bytes(8))))
    sp = client.get_suggested_params()
    
    if loan['borrowing_id'] != 0:
        sp.fee = sp.min_fee * 2
        client.call(opt_into_nft, asset = loan['borrowing_id'], suggested_params=sp)
        

        axfer = TransactionWithSigner(
            txn=transaction.AssetTransferTxn(
                sender=sender.address,
                receiver=client.app_addr,
                index=loan['borrowing_id'],
                amt= loan['amount'],
                sp=sp,
            ),
            signer=sender.signer,
        )
        sp.fee = sp.min_fee * 2
        client.call(propose_interest,loan_id = loan_id,axfer=axfer, proposed_interest= proposal, suggested_params =sp , boxes = [(app_id, int(loan_id).to_bytes(8))])
    else:

        paytx =TransactionWithSigner(
            txn = transaction.PaymentTxn(
                sender=sender.address,
                receiver = client.app_addr,
                amt = loan['amount'],
                sp = client.get_suggested_params()
            ),
            signer = sender.signer
        )
        sp.fee = sp.min_fee * 2
        client.call(propose_native_interest,loan_id = loan_id,paytx= paytx , proposed_interest= proposal, suggested_params =sp , boxes = [(app_id, int(loan_id).to_bytes(8))])   

def revokeProposal(algod_client: AlgodClient, app_id, loan_id, sender):
    client = ApplicationClient(
        client= algod_client,
        app= app,
        signer= sender.signer,
        app_id= app_id,
    )
    loan = formatLoan(unpackBox(algod_client.application_box_by_name(app_id, int(loan_id).to_bytes(8))))

    sp = client.get_suggested_params()
    sp.fee = sp.min_fee * 2
    client.call(revoke_proposal,loan_id = loan_id, suggested_params =sp , boxes = [(app_id, int(loan_id).to_bytes(8))], foreign_assets=[loan['borrowing_id']], accounts=[loan['proposer']])

def acceptProposal(algod_client: AlgodClient, app_id, loan_id, sender):
    client = ApplicationClient(
        client= algod_client,
        app= app,
        signer= sender.signer,
        app_id= app_id,
    )
    loan = formatLoan(unpackBox(algod_client.application_box_by_name(app_id, int(loan_id).to_bytes(8))))

    sp = client.get_suggested_params()
    sp.fee = sp.min_fee * 2
    client.call(accept_proposal,loan_id = loan_id, suggested_params =sp , boxes = [(app_id, int(loan_id).to_bytes(8))], accounts=[loan['proposer']], foreign_assets=[loan['borrowing_id']])

##### Tests

@pytest.mark.deploy
def test_deploy(algod_client: AlgodClient):
    user = generate_funded_account(algod_client)
    client = ApplicationClient(algod_client, app, signer=user.signer, sender=user.address)
    app_id, _, _ = client.create()
    assert app_id != 0
    
def test_acceptLoan(algod_client: AlgodClient):
    requester = generate_funded_account(algod_client)
    user = generate_funded_account(algod_client)
    other_user = generate_funded_account(algod_client)
    client = ApplicationClient(algod_client, app, signer=user.signer, sender=user.address)
    app_id, _, _ = client.create()

    nft = create_nft(algod_client, requester)
    nft2 = create_nft(algod_client, requester)
    token_id = create_asset(algod_client, user)
    # Create a loan request and ask for 1000 token_id tokens
    requestLoan(algod_client, app_id, nft, 1000, token_id, 100000, 100, requester)
    available_loans = getAvailableLoans(algod_client, app_id, True)
    assert len(available_loans) == 1
    assert available_loans[0] == 1
    
    # Create a 2nd loan and ask for native tokens
    requestLoan(algod_client, app_id, nft2, 1_000_000, 0, 100000, 100, requester)
    
    available_loans = getAvailableLoans(algod_client, app_id, True)
    assert len(available_loans) == 2
    
    # User will accept loan with id 1
    balance_before = algod_client.account_asset_info(requester.address, token_id)['asset-holding']['amount']
    acceptLoan(algod_client, app_id, 1, user)
    balance_after = algod_client.account_asset_info(requester.address, token_id)['asset-holding']['amount']
    
    acceptedLoan = formatLoanById(algod_client, app_id, 1)
    available_loans = getAvailableLoans(algod_client, app_id, True)
    assert acceptedLoan['start'] > 0
    assert acceptedLoan['lender'] == user.address
    assert available_loans[0] == 2
    assert len(available_loans) == 1
    assert balance_after - balance_before == 1000
    
    # User will accept the 2nd loan too
    algo_balance_before = algod_client.account_info(requester.address)['amount']
    acceptLoan(algod_client, app_id, 2, other_user)
    algo_balance_after = algod_client.account_info(requester.address)['amount']
    acceptedLoan = formatLoanById(algod_client, app_id, 2)
    
    assert acceptedLoan['start'] > 0
    assert acceptedLoan['lender'] == other_user.address
    assert algo_balance_after - algo_balance_before == 1_000_000
    assert len(getAvailableLoans(algod_client, app_id, True)) == 0

def test_deleteRequest(algod_client: AlgodClient):
    requester = generate_funded_account(algod_client)
    malicious_user = generate_funded_account(algod_client)
    
    client = ApplicationClient(algod_client, app, signer=requester.signer, sender=requester.address)
    app_id, app_addr, _ = client.create()

    nft = create_nft(algod_client, requester)
    nft2 = create_nft(algod_client, requester)
    
    token_id = create_asset(algod_client, malicious_user)
    
    assert algod_client.account_asset_info(requester.address, nft)['asset-holding']['amount'] == 1
    assert algod_client.account_asset_info(requester.address, nft2)['asset-holding']['amount'] == 1
    
    requestLoan(algod_client, app_id, nft, 1000, token_id, 100000, 100, requester)
    requestLoan(algod_client, app_id, nft2, 1_000_000, 0, 100000, 100, requester)
    
    assert len(getAvailableLoans(algod_client, app_id, True)) == 2
    # NFTs should be transferred to app
    assert algod_client.account_asset_info(requester.address, nft)['asset-holding']['amount'] == 0
    assert algod_client.account_asset_info(requester.address, nft2)['asset-holding']['amount'] == 0
    # malicious user should not be able to delete other request
    try:
        deleteRequest(algod_client, app_id, 1, malicious_user)
        assert False
    except LogicError:
        pass
    
    # Delete request 1
    deleteRequest(algod_client, app_id, 1, requester)
    # User should get the NFT back
    assert algod_client.account_asset_info(requester.address, nft)['asset-holding']['amount'] == 1
    assert algod_client.account_asset_info(requester.address, nft2)['asset-holding']['amount'] == 0
    
    available_loans = getAvailableLoans(algod_client, app_id, True)
    assert available_loans[0] == 2
    assert len(available_loans) == 1
    
    # Malicious user should not be able to accept loan 1
    try:
        acceptLoan(algod_client, app_id, 1, malicious_user)
        assert False
    except error.AlgodHTTPError:
        # Box not exists error
        pass
    
    # Delete request 2 too
    deleteRequest(algod_client, app_id, 2, requester)
    # User should get the NFT back
    assert algod_client.account_asset_info(requester.address, nft)['asset-holding']['amount'] == 1
    assert algod_client.account_asset_info(requester.address, nft2)['asset-holding']['amount'] == 1
    
    assert len(getAvailableLoans(algod_client, app_id, True)) == 0
    
def test_DeleteAfterAccept(algod_client: AlgodClient):
    requester = generate_funded_account(algod_client)
    user = generate_funded_account(algod_client)
    
    client = ApplicationClient(algod_client, app, signer=requester.signer, sender=requester.address)
    app_id, _, _ = client.create()

    nft = create_nft(algod_client, requester)
    
    token_id = create_asset(algod_client, user)
    
    # Create a request from requester, user accepts it and then requester tries to delete.
    requestLoan(algod_client, app_id, nft, 1000, token_id, 100000, 100, requester)

    acceptLoan(algod_client, app_id, 1, user)
    try:
        deleteRequest(algod_client, app_id, 1, requester)
        assert False
    except LogicError:
        pass
    
def test_repayLoan(algod_client: AlgodClient):
    requester = generate_funded_account(algod_client)
    user = generate_funded_account(algod_client)
    other_user = generate_funded_account(algod_client)
    
    client = ApplicationClient(algod_client, app, signer=user.signer, sender=user.address)
    app_id, _, _ = client.create()

    nft = create_nft(algod_client, requester)
    token_id = create_asset(algod_client, user)
    
    # Transfer some tokens to other user for testing
    opt_in_asset(algod_client, other_user, token_id)
    asset_transfer(algod_client, user, other_user.address, token_id, 10000)

    requestLoan(algod_client, app_id, nft, 1000, token_id, 0, 100, requester)
    acceptLoan(algod_client, app_id, 1, user)
    
    assert algod_client.account_asset_info(requester.address, token_id)['asset-holding']['amount'] == 1000
    assert algod_client.account_asset_info(requester.address, nft)['asset-holding']['amount'] == 0
    
    user_balance_before = algod_client.account_asset_info(user.address, token_id)['asset-holding']['amount']
    
    # Other user tries to pay back instead of requester
    try:
        repayLoan(algod_client, app_id, 1, other_user)
        assert False
    except LogicError:
        pass
    
    # requester repays
    repayLoan(algod_client, app_id, 1, requester)
    
    user_balance_after = algod_client.account_asset_info(user.address, token_id)['asset-holding']['amount']
    
    assert algod_client.account_asset_info(requester.address, token_id)['asset-holding']['amount'] == 0
    assert algod_client.account_asset_info(requester.address, nft)['asset-holding']['amount'] == 1
    assert user_balance_after - user_balance_before == 1000
    
def test_liquidateLoan(algod_client: AlgodClient):
    requester = generate_funded_account(algod_client)
    user = generate_funded_account(algod_client)
    other_user = generate_funded_account(algod_client)
    
    client = ApplicationClient(algod_client, app, signer=user.signer, sender=user.address)
    app_id, _, _ = client.create()

    nft = create_nft(algod_client, requester)
    nft2 = create_nft(algod_client, requester)
    token_id = create_asset(algod_client, user)

    requestLoan(algod_client, app_id, nft, 1000, token_id, 0, 100, requester)
    requestLoan(algod_client, app_id, nft2, 1000, token_id, 100000, 100, requester)
    acceptLoan(algod_client, app_id, 1, user)
    acceptLoan(algod_client, app_id, 2, user)
    # Ensure only lender can liquidate
    try:
        liquidateLoan(algod_client, app_id, 1, other_user)
        assert False
    except LogicError:
        pass
    
    # When liquidating:
    # 1. lender get's the NFT
    # 2. The box is deleted, thus repay etc are not possible
    # 3. Requester get's back the Box's mbr
    requester_balance_before = algod_client.account_info(requester.address)['amount']
    liquidateLoan(algod_client, app_id, 1, user)
    requester_balance_after = algod_client.account_info(requester.address)['amount']
    
    assert algod_client.account_asset_info(user.address, nft)['asset-holding']['amount'] == 1
    assert requester_balance_after > requester_balance_before
    
    try:
        repayLoan(algod_client, app_id, 1, requester)
        assert False
    except error.AlgodHTTPError:
        pass
    
    # Liquidating the 2nd loan must fail
    try:
        liquidateLoan(algod_client, app_id, 2, user)
        assert False
    except LogicError:
        pass

def test_proposeInterest(algod_client: AlgodClient):
    requester = generate_funded_account(algod_client)
    proposer = generate_funded_account(algod_client)
    
    client = ApplicationClient(algod_client, app, signer=requester.signer, sender=requester.address)
    app_id, _, _ = client.create()

    nft = create_nft(algod_client, requester)
    token_id = create_asset(algod_client, proposer)
    # Create a loan request and ask for 1000 token_id tokens
    requestLoan(algod_client, app_id, nft, 1000, token_id, 100000, 100, requester)
    
    proposer_init_balance = algod_client.account_asset_info(proposer.address, token_id)['asset-holding']['amount']
    # lender wants more interest
    proposeInterest(algod_client, app_id, 1, 200, proposer)
    
    loan_info = formatLoanById(algod_client, app_id, 1)
    assert loan_info['proposed_interest'] == 200
    assert loan_info['proposer'] == proposer.address
    # ASAs should be transferred to contract
    assert algod_client.account_asset_info(client.app_addr, token_id)['asset-holding']['amount'] == 1000
    assert proposer_init_balance - algod_client.account_asset_info(proposer.address, token_id)['asset-holding']['amount'] == 1000
    
def test_RevokeProposalOwner(algod_client: AlgodClient):
    requester = generate_funded_account(algod_client)
    proposer = generate_funded_account(algod_client)
    malicious_user = generate_funded_account(algod_client)
    
    client = ApplicationClient(algod_client, app, signer=requester.signer, sender=requester.address)
    app_id, _, _ = client.create()

    nft = create_nft(algod_client, requester)
    token_id = create_asset(algod_client, proposer)
    # Create a loan request and ask for 1000 token_id tokens
    requestLoan(algod_client, app_id, nft, 1000, token_id, 100000, 100, requester)
    
    proposer_init_balance = algod_client.account_asset_info(proposer.address, token_id)['asset-holding']['amount']
    # lender wants more interest
    proposeInterest(algod_client, app_id, 1, 200, proposer)
    # Only proposer or owner can revoke
    try:
        revokeProposal(algod_client, app_id, 1, malicious_user)
        assert False
    except LogicError:
        pass
    
    # Owner revokes proposal
    revokeProposal(algod_client, app_id, 1, requester)

    # Proposer should get his ASAs back
    assert algod_client.account_asset_info(proposer.address, token_id)['asset-holding']['amount'] == proposer_init_balance
    loan_info = formatLoanById(algod_client, app_id, 1)
    assert loan_info['proposed_interest'] == 0
    assert loan_info['proposer'] == constants.ZERO_ADDRESS
    assert algod_client.account_asset_info(client.app_addr, token_id)['asset-holding']['amount'] == 0

def test_RevokeProposalProposer(algod_client: AlgodClient):
    requester = generate_funded_account(algod_client)
    proposer = generate_funded_account(algod_client)
    
    client = ApplicationClient(algod_client, app, signer=requester.signer, sender=requester.address)
    app_id, _, _ = client.create()

    nft = create_nft(algod_client, requester)
    # ask for ALGOs
    requestLoan(algod_client, app_id, nft, 1_000_000, 0, 100000, 100, requester)
    
    proposer_init_balance = algod_client.account_info(proposer.address)['amount']
    app_init_balance = algod_client.account_info(client.app_addr)['amount']
    
    # lender wants more interest
    proposeInterest(algod_client, app_id, 1, 200, proposer)
    # There should be quite a change in proposer's balance and app should have more than 1 ALGO
    assert proposer_init_balance > algod_client.account_info(proposer.address)['amount'] + 1_000_000
    assert algod_client.account_info(client.app_addr)['amount'] - app_init_balance == 1_000_000

    proposer_init_balance = algod_client.account_info(proposer.address)['amount']
    
    # Proposer revokes proposal
    revokeProposal(algod_client, app_id, 1, proposer)

    # # Proposer should get his ASAs back
    loan_info = formatLoanById(algod_client, app_id, 1)
    assert loan_info['proposed_interest'] == 0
    assert loan_info['proposer'] == constants.ZERO_ADDRESS
    assert app_init_balance == algod_client.account_info(client.app_addr)['amount']

def test_AcceptProposal(algod_client: AlgodClient):
    requester = generate_funded_account(algod_client)
    proposer = generate_funded_account(algod_client)
    
    client = ApplicationClient(algod_client, app, signer=requester.signer, sender=requester.address)
    app_id, _, _ = client.create()

    nft = create_nft(algod_client, requester)
    token_id = create_asset(algod_client, proposer)
    # Create a loan request and ask for 1000 token_id tokens
    requestLoan(algod_client, app_id, nft, 1000, token_id, 100000, 100, requester)
    
    # lender wants more interest
    proposeInterest(algod_client, app_id, 1, 200, proposer)
    
    # requester accepts proposal
    acceptProposal(algod_client, app_id, 1, requester)
    
    # Loan is now accepted
    loan_info = formatLoanById(algod_client, app_id, 1)
    assert loan_info['interest'] == 200
    assert loan_info['lender'] == proposer.address
    assert algod_client.account_asset_info(requester.address, token_id)['asset-holding']['amount'] == 1000
    assert len(getAvailableLoans(algod_client, app_id, True)) == 0
    
def test_AcceptLoanWithProposal(algod_client: AlgodClient):
    requester = generate_funded_account(algod_client)
    proposer = generate_funded_account(algod_client)
    user = generate_funded_account(algod_client)
    
    client = ApplicationClient(algod_client, app, signer=requester.signer, sender=requester.address)
    app_id, _, _ = client.create()

    nft = create_nft(algod_client, requester)
    token_id = create_asset(algod_client, proposer)
    # Transfer tokens to user
    opt_in_asset(algod_client, user, token_id)
    asset_transfer(algod_client, proposer, user.address, token_id, 10_000_000)
    
    proposer_init_balance = algod_client.account_asset_info(proposer.address, token_id)['asset-holding']['amount']
    
    # Create a loan request and ask for 1000 token_id tokens
    requestLoan(algod_client, app_id, nft, 1000, token_id, 100000, 100, requester)
    proposeInterest(algod_client, app_id, 1, 200, proposer)
    
    # User accept's the loan at the initial interest
    acceptLoan(algod_client, app_id, 1, user)
    
    # Proposer gets his tokens back and the loan is now accepted by user
    loan = formatLoanById(algod_client, app_id, 1)
    assert algod_client.account_asset_info(proposer.address, token_id)['asset-holding']['amount'] == proposer_init_balance
    assert algod_client.account_asset_info(requester.address, token_id)['asset-holding']['amount'] == 1000
    assert algod_client.account_asset_info(user.address, token_id)['asset-holding']['amount'] == 10_000_000 - 1000
    assert loan['interest'] == 100
    assert loan['start'] > 0
    assert loan['lender'] == user.address
    assert len(getAvailableLoans(algod_client, app_id, True)) == 0