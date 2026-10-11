import Head from 'next/head'
import StrategyValidationPanel from '../components/StrategyValidationPanel'

export default function StrategyValidationPage() {
  return (
    <>
      <Head>
        <title>Strategy Validation Engine · Sentinel</title>
        <meta name="description" content="Research-only historical strategy validation prototype" />
      </Head>
      <StrategyValidationPanel />
    </>
  )
}
