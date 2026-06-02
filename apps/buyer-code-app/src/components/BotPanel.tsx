import { useState } from 'react'
import {
  makeStyles,
  tokens,
  Button,
  OverlayDrawer,
  DrawerHeader,
  DrawerHeaderTitle,
  DrawerBody,
} from '@fluentui/react-components'
import { ChatRegular, DismissRegular } from '@fluentui/react-icons'

const BOT_URL = import.meta.env.VITE_COPILOT_BOT_URL as string | undefined

const useStyles = makeStyles({
  fab: {
    position: 'fixed',
    bottom: '24px',
    right: '24px',
    zIndex: 1000,
    width: '52px',
    height: '52px',
    borderRadius: '50%',
    boxShadow: tokens.shadow16,
  },
  drawerBody: {
    padding: 0,
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
  },
  iframe: {
    flex: 1,
    border: 'none',
    width: '100%',
    height: '100%',
  },
  placeholder: {
    padding: '24px',
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
    color: tokens.colorNeutralForeground2,
    fontSize: '13px',
    lineHeight: '20px',
  },
  placeholderTitle: {
    fontWeight: '600',
    color: tokens.colorNeutralForeground1,
    fontSize: '14px',
  },
  code: {
    fontFamily: 'monospace',
    backgroundColor: tokens.colorNeutralBackground3,
    padding: '8px 12px',
    borderRadius: '4px',
    fontSize: '12px',
    color: tokens.colorBrandForeground1,
  },
})

export default function BotPanel() {
  const styles = useStyles()
  const [open, setOpen] = useState(false)

  return (
    <>
      <Button
        appearance="primary"
        icon={<ChatRegular fontSize={22} />}
        className={styles.fab}
        onClick={() => setOpen(true)}
        title="Open MarketBot"
      />

      <OverlayDrawer
        open={open}
        onOpenChange={(_, { open: o }) => setOpen(o)}
        position="end"
        size="medium"
      >
        <DrawerHeader>
          <DrawerHeaderTitle
            action={
              <Button
                appearance="subtle"
                icon={<DismissRegular />}
                onClick={() => setOpen(false)}
              />
            }
          >
            MarketBot
          </DrawerHeaderTitle>
        </DrawerHeader>

        <DrawerBody className={styles.drawerBody}>
          {BOT_URL ? (
            <iframe
              className={styles.iframe}
              src={BOT_URL}
              title="MarketBot"
              allow="microphone"
            />
          ) : (
            <div className={styles.placeholder}>
              <div className={styles.placeholderTitle}>MarketBot not configured</div>
              <p>
                Publish the agent in Copilot Studio, copy the embed URL, then add it to{' '}
                <code>apps/buyer-code-app/.env.local</code>:
              </p>
              <div className={styles.code}>
                VITE_COPILOT_BOT_URL=https://web.powerva.microsoft.com/environments/…/webchat
              </div>
              <p>
                See <strong>docs/copilot-studio-spec.md</strong> Part 3 for full instructions.
              </p>
            </div>
          )}
        </DrawerBody>
      </OverlayDrawer>
    </>
  )
}
