import { makeStyles, tokens, Text, Badge } from '@fluentui/react-components'
import { ChartMultipleRegular } from '@fluentui/react-icons'

const PBI_WORKSPACE_URL = (import.meta.env.VITE_PBI_WORKSPACE_URL as string | undefined) || ''
const REPORTS = import.meta.env.VITE_PBI_REPORTS as string | undefined

const useStyles = makeStyles({
  root: {
    padding: '24px',
    display: 'flex',
    flexDirection: 'column',
    gap: '24px',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  title: {
    fontSize: '20px',
    fontWeight: '600',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(480px, 1fr))',
    gap: '16px',
  },
  tile: {
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: '8px',
    overflow: 'hidden',
    backgroundColor: tokens.colorNeutralBackground2,
  },
  tileHeader: {
    padding: '12px 16px',
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    fontWeight: '600',
    fontSize: '13px',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  iframe: {
    width: '100%',
    height: '320px',
    border: 'none',
    display: 'block',
  },
  placeholder: {
    height: '320px',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
    color: tokens.colorNeutralForeground3,
    fontSize: '13px',
    padding: '24px',
    textAlign: 'center',
  },
  link: {
    color: tokens.colorBrandForeground1,
    textDecoration: 'none',
    fontWeight: '500',
  },
  notice: {
    padding: '12px 16px',
    backgroundColor: tokens.colorNeutralBackground3,
    borderRadius: '6px',
    fontSize: '13px',
    color: tokens.colorNeutralForeground2,
    lineHeight: '20px',
  },
})

const REPORT_SLOTS = [
  { key: 'regional_demand', label: 'Regional Demand' },
  { key: 'supplier_scorecard', label: 'Supplier Scorecard' },
  { key: 'top_moving_skus', label: 'Top-Moving SKUs' },
  { key: 'price_spread', label: 'Price Spread' },
] as const

function parseReportUrls(): Record<string, string> {
  if (!REPORTS) return {}
  try {
    return JSON.parse(REPORTS) as Record<string, string>
  } catch {
    return {}
  }
}

export default function Insights() {
  const styles = useStyles()
  const reportUrls = parseReportUrls()
  const configured = Object.keys(reportUrls).length > 0

  return (
    <div className={styles.root}>
      <div className={styles.header}>
        <ChartMultipleRegular fontSize={24} />
        <Text className={styles.title}>Market Intelligence</Text>
        {configured && <Badge appearance="filled" color="success">Live</Badge>}
      </div>

      {!configured && (
        <div className={styles.notice}>
          Power BI reports are not yet embedded. After building reports in the{' '}
          <a
            className={styles.link}
            href={PBI_WORKSPACE_URL}
            target="_blank"
            rel="noreferrer"
          >
            B2BAgg-Analytics workspace
          </a>
          , copy each report embed URL and add to <code>.env.local</code> as{' '}
          <code>VITE_PBI_REPORTS</code> (JSON map). See{' '}
          <strong>powerbi/SETUP.md</strong> for details.
        </div>
      )}

      <div className={styles.grid}>
        {REPORT_SLOTS.map(({ key, label }) => (
          <div key={key} className={styles.tile}>
            <div className={styles.tileHeader}>{label}</div>
            {reportUrls[key] ? (
              <iframe
                className={styles.iframe}
                src={reportUrls[key]}
                title={label}
                allowFullScreen
              />
            ) : (
              <div className={styles.placeholder}>
                <ChartMultipleRegular fontSize={32} />
                <span>Report not yet configured</span>
                <span style={{ fontSize: '11px' }}>Key: <code>{key}</code></span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
