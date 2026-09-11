# RewardBank - Writeup

## 1. Assumptions I made

This is a one-day project, so I kept the design simple and focused on the main requirements.

### Balance

I treat the ledger as the main record of the child's balance.

Whenever the balance changes, I create a ledger entry.

- Task reward adds minutes.
- Usage removes minutes.
- Undo approval removes the remaining reward.
- I never directly change the balance without creating a ledger entry.

For example, if a child gets 30 minutes and then uses 10 and 20 minutes, the balance is:

**30 - 10 - 20 = 0 minutes**

The sum of all ledger entries should always be the same as the current balance.

### Tasks

I use these task statuses:

**CREATED → DONE → APPROVED**

A task can also be rejected:

**CREATED → DONE → REJECTED**

A task can only be marked as done when it is in `CREATED` state.

A task can only be approved or rejected when it is in `DONE` state.

A reward is added only when the task is approved.

### Usage sessions

Every usage session has a unique `session_id`.

I use this ID to handle duplicate requests. If the same session is sent again, it is not charged again.

Usage is calculated from the session start and end time.

If the child has enough balance, the complete session is covered.

If the child does not have enough balance, only the available minutes are covered and the remaining minutes are rejected.

The API also returns the exact `cutoff_time` when the balance reaches zero.

I allow late usage reports because a device can be offline and send the session later.

---

## 2. What happens if the parent clicks Approve twice?

The approve operation is idempotent.

If the parent approves the same task twice, the reward is only added once.

For example, for a task with a 30 minute reward:

First approval:

- Task changes to `APPROVED`
- `+30` is added to the ledger
- Balance becomes 30

Second approval:

- No new ledger entry is created
- Balance stays 30
- API returns `ALREADY_APPROVED`

I wrote tests for this behaviour.

The tests include:

- `test_approve_is_idempotent`
- `test_double_approval_does_not_double_reward`

This is important because a parent can accidentally click the button twice, or the same request can be sent again because of a network retry.

---

## 3. Two usage sessions happen at the same time

Suppose the child has 20 minutes left.

YouTube reports 15 minutes and another game reports 10 minutes.

Together they need 25 minutes, but only 20 minutes are available.

The service processes one request first.

### First request

YouTube uses 15 minutes.

Balance:

**20 - 15 = 5 minutes**

A `USAGE` ledger entry of `-15` is created.

### Second request

The game asks for 10 minutes, but only 5 minutes are left.

So:

- 5 minutes are covered
- 5 minutes are rejected
- Balance becomes 0

A `USAGE` ledger entry of `-5` is created.

The important part is that the balance never becomes negative.

The response for the second session also contains the cutoff timestamp where the balance reached zero.

The order is based on which usage request is processed first. In a real production system I would also use database transactions and proper locking to make this safe when many requests happen at the same time.

---

## 4. My undo approval design

I do not delete the original reward from the ledger.

Instead, I create a new ledger entry called `UNDO_APPROVAL`.

This keeps the complete history of what happened.

For example, if the parent approved a task for 20 minutes:

- `TASK_REWARD +20`

If the parent later wants to undo it:

- `UNDO_APPROVAL -20`

This brings the balance back to the previous value.

### What if the child already spent some of the reward?

Suppose the child received 20 minutes and already spent 10 minutes.

The balance is now 10.

If the parent undoes the approval, I remove only the 10 minutes that are still available.

The ledger becomes:

- `TASK_REWARD +20`
- `USAGE -10`
- `UNDO_APPROVAL -10`

The final balance is 0.

I chose this because I don't want the child's balance to become negative because of a parent correction.

For a parent-child product, I think this is better than creating a negative screen-time balance for the child.

The original reward and the usage history are still present in the ledger, so we can see what actually happened.

If the complete reward was already spent, there are no minutes left to remove, so the undo does not create a negative balance.

---

## 5. What would break first with 100,000 children?

My current implementation uses SQLite and is mainly designed for this assessment.

With 100,000 children and usage events coming continuously, the first problem would be database load and concurrent updates.

Many devices could send usage for the same child at the same time.

The current simple SQLite setup would not be the best choice for that scale.

I would move to PostgreSQL.

I would also use database transactions and proper locking when changing the balance.

I would make `session_id` unique in the database so duplicate usage requests cannot be processed twice.

I would also add indexes for frequently used fields such as `child_id`.

A larger system could look like:

API → Queue → Workers → Database → Ledger

The important rule would still stay the same:

**Sum of ledger amounts must equal the current balance.**

---

## 6. What I deliberately did not build

Because this was a one-day assessment, I focused on the core accounting logic, API, tests and simulator.

### Full authentication

I did not build a complete login system.

The assignment only requires simple token authentication, so I kept authentication simple.

With more time I would add:

- Password hashing
- Proper login
- JWT or sessions
- Token expiry
- Better role based authorization

### Production database

I used SQLite because it was simple to set up and enough for this assessment.

With more time I would move to PostgreSQL and add:

- Database migrations
- Better indexes
- Transactions
- Concurrency handling
- Backup and recovery

### Real device integration

I did not build a real mobile application or device integration because it was not required.

Instead, I created a simulator which behaves like devices sending usage sessions.

The simulator includes:

- Normal usage
- Duplicate usage reports
- Late usage reports
- Usage with zero balance
- Multiple apps using the same balance
- Wrong approval and undo approval

### Notifications

I did not build notifications.

With more time, parents could receive notifications when:

- A child completes a task
- A task is approved
- Balance reaches zero
- An approval is undone

### Frontend

I did not build a frontend because the assessment does not require one.

The API can be tested through Swagger and the complete flow can be seen using the demo script.

### Reports

I did not build analytics or reports.

With another week, I could add daily screen-time reports, app-wise usage, earned minutes and task history.

---

## Final thoughts

The main thing I focused on in this project is keeping the accounting correct.

Every balance change creates a ledger entry.

For example:

**TASK_REWARD +30**  
**USAGE -10**  
**USAGE -20**

The final balance is 0.

I also tried to handle real-world problems such as:

- Duplicate approval requests
- Duplicate usage reports
- Late usage reports
- Usage after balance reaches zero
- Multiple apps competing for the same balance
- Undoing an approval after some minutes were already spent

I wrote tests for the important cases and also check the ledger invariant in the demo.

The main rule of the system is:

**Sum of all ledger entries = current balance**

This invariant is checked by the tests and by the end-to-end demo.