## Modals: forms, not commands

```python
class FeedbackModal(discord.ui.Modal, title="Feedback"):
    feedback = discord.ui.TextInput(
        label="What should we improve?",
        style=discord.TextStyle.paragraph,  # TextStyle, not TextInputStyle
        max_length=500,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await save_feedback(interaction.user.id, self.feedback.value)
        await interaction.response.send_message(
            "Thanks, saved.", ephemeral=True
        )

@app_commands.command(name="feedback", description="Send feedback.")
async def feedback(self, interaction: discord.Interaction) -> None:
    await interaction.response.send_modal(FeedbackModal())
```

- `TextInputStyle` **does not exist** in current discord.py
  (verified on 2.7.1: neither `discord.TextInputStyle` nor
  `discord.ui.TextInputStyle` exists). It was renamed to
  `discord.TextStyle` (`.short`, `.paragraph`). The version the
  rename happened in is UNVERIFIED: the changelog text fetched has
  no `TextStyle` hit. Old tutorials using `TextInputStyle` fail
  with an AttributeError.
- A modal holds at most 5 items (discord.py changelog v2.7.0:
  Modal raises when hitting the 5 item limit). Count the inputs,
  selects, and labels before you send it.
- A modal is opened with `interaction.response.send_modal()`, never
  with `send_message`. The modal's `on_submit` answers the
  interaction; a modal that never answers leaves the user staring at
  a spinner.
- Validate in `on_submit`, not in the modal definition. A modal
  cannot reject input before submit; check it, and answer the user
  with what was wrong.
