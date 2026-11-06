## Tests must be able to fail

A test that cannot fail proves nothing. These are the ways tests
written by an AI usually lie:

- **Asserting what the code does, not what it should do.** Expected
  values come from the spec or a worked example, never by
  recomputing the value the way the code does. A test that asserts
  `add(a, b) == a + b` passes by construction and can never catch
  a bug.
- **Asserting truthiness instead of values.** `assert result`
  passes for any non-empty value. Assert the exact value:
  `assert balance == 60`.
- **Mocking the unit under test.** If the test mocks the function
  it is testing, it tests the mock. Mock the boundary (Discord,
  the database, the clock), never the code under test.
- **Only testing the happy path.** Every command needs an error-path
  test: `MissingPermissions`, `discord.Forbidden`, invalid input.
  An interaction timeout has no testable exception, so it belongs
  in live verification (see "Verify live"), not in the suite. A bot
  crashes on the paths nobody tested.
- **Writing tests after the fix.** Write the failing test first,
  watch it fail, then fix the code. A test written after the fix
  often asserts the bug as correct behavior.

Before trusting a suite, break something on purpose: change one
expected value and confirm the test goes red. If it stays green,
the test is decoration.
