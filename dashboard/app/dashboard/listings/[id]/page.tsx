import { notFound } from 'next/navigation'
import Link from 'next/link'
import { getDb } from '@/lib/mongodb'
import { ObjectId } from 'mongodb'

interface Props {
  params: { id: string }
}

export default async function ListingDetailPage({ params }: Props) {
  let listing = null
  let db = null
  try {
    db = await getDb()
    if (!db) throw new Error('DB not available')
    const id = params.id.includes('-') ? params.id : params.id
    listing = await db.collection('listings').findOne({ _id: new ObjectId(id) })
  } catch (e) {
    notFound()
  }

  if (!listing) notFound()

  const scoreBreakdown = listing.score_breakdown || {}
  const breakdownEntries = typeof scoreBreakdown === 'object' && !Array.isArray(scoreBreakdown)
    ? Object.entries(scoreBreakdown)
    : []

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow p-6">
        <h1 className="text-2xl font-bold mb-2 text-gray-900 dark:text-white">{listing.title || 'Listing'}</h1>
        <p className="text-gray-600 dark:text-gray-400 mb-4">{listing.address || listing.bezirk || 'Vienna'}</p>

        <div className="grid grid-cols-2 gap-4 mb-6">
          <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded">
            <span className="text-sm text-gray-500 dark:text-gray-400">Price</span>
            <p className="font-semibold text-gray-900 dark:text-white">
              {listing.price_total ? `€${listing.price_total.toLocaleString()}` : 'N/A'}
            </p>
          </div>
          <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded">
            <span className="text-sm text-gray-500 dark:text-gray-400">Area</span>
            <p className="font-semibold text-gray-900 dark:text-white">
              {listing.area_m2 ? `${listing.area_m2}m²` : 'N/A'}
            </p>
          </div>
          <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded">
            <span className="text-sm text-gray-500 dark:text-gray-400">Rooms</span>
            <p className="font-semibold text-gray-900 dark:text-white">
              {listing.rooms || 'N/A'}
            </p>
          </div>
          <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded">
            <span className="text-sm text-gray-500 dark:text-gray-400">District</span>
            <p className="font-semibold text-gray-900 dark:text-white">
              {listing.bezirk || 'N/A'}
            </p>
          </div>
          <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded">
            <span className="text-sm text-gray-500 dark:text-gray-400">Score</span>
            <p className="font-semibold text-green-600">
              {listing.score ? `${listing.score}/100` : 'N/A'}
            </p>
          </div>
          <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded">
            <span className="text-sm text-gray-500 dark:text-gray-400">Energy Class</span>
            <p className="font-semibold text-gray-900 dark:text-white">
              {listing.energy_class || listing.hwb_value ? `${listing.energy_class || 'HWB: ' + listing.hwb_value}` : 'N/A'}
            </p>
          </div>
        </div>

        {breakdownEntries.length > 0 && (
          <div className="mb-6">
            <h2 className="text-lg font-semibold mb-3 text-gray-900 dark:text-white">Score Breakdown</h2>
            <div className="space-y-2">
              {breakdownEntries.map(([key, data]: [string, any]) => (
                <div key={key} className="flex justify-between items-center p-2 bg-gray-50 dark:bg-gray-800 rounded">
                  <span className="text-gray-700 dark:text-gray-300 capitalize">{key.replace(/_/g, ' ')}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-24 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-green-500"
                        style={{ width: `${typeof data === 'object' ? (data.normalized_score || 0) : 0}%` }}
                      />
                    </div>
                    <span className="text-sm font-medium text-gray-900 dark:text-white">
                      {typeof data === 'object' ? (data.normalized_score || 0) : 0}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="flex gap-4">
          <a
            href={listing.url}
            target="_blank"
            rel="noopener noreferrer"
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded transition-colors"
          >
            View on {listing.source || 'Source'}
          </a>
          <Link
            href="/dashboard"
            className="bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-800 dark:text-white px-4 py-2 rounded transition-colors"
          >
            Back to Dashboard
          </Link>
        </div>
      </div>
    </div>
  )
}