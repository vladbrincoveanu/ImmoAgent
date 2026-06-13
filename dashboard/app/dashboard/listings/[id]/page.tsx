import { notFound } from 'next/navigation'
import Link from 'next/link'
import { getDb } from '@/lib/mongodb'
import { ObjectId } from 'mongodb'

interface Props {
  params: Promise<{ id: string }>
}

export default async function ListingDetailPage({ params }: Props) {
  const { id: rawId } = await params
  let listing = null
  let db = null
  try {
    db = await getDb()
    if (!db) throw new Error('DB not available')
    const id = rawId.includes('-') ? rawId : rawId
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
      <div className="bg-white rounded-lg shadow p-6">
        <h1 className="text-2xl font-bold mb-2 text-[#3D405B]">{listing.title || 'Listing'}</h1>
        <p className="text-[#8B8B8B] mb-4">{listing.address || listing.bezirk || 'Vienna'}</p>

        <div className="grid grid-cols-2 gap-4 mb-6">
          <div className="p-3 bg-[#F9F7F4] rounded">
            <span className="text-sm text-[#8B8B8B]">Price</span>
            <p className="font-semibold text-[#3D405B]">
              {listing.price_total ? `€${listing.price_total.toLocaleString()}` : 'N/A'}
            </p>
          </div>
          <div className="p-3 bg-[#F9F7F4] rounded">
            <span className="text-sm text-[#8B8B8B]">Area</span>
            <p className="font-semibold text-[#3D405B]">
              {listing.area_m2 ? `${listing.area_m2}m²` : 'N/A'}
            </p>
          </div>
          <div className="p-3 bg-[#F9F7F4] rounded">
            <span className="text-sm text-[#8B8B8B]">Rooms</span>
            <p className="font-semibold text-[#3D405B]">
              {listing.rooms || 'N/A'}
            </p>
          </div>
          <div className="p-3 bg-[#F9F7F4] rounded">
            <span className="text-sm text-[#8B8B8B]">District</span>
            <p className="font-semibold text-[#3D405B]">
              {listing.bezirk || 'N/A'}
            </p>
          </div>
          <div className="p-3 bg-[#F9F7F4] rounded">
            <span className="text-sm text-[#8B8B8B]">Score</span>
            <p className="font-semibold text-green-600">
              {listing.score ? `${listing.score}/100` : 'N/A'}
            </p>
          </div>
          <div className="p-3 bg-[#F9F7F4] rounded">
            <span className="text-sm text-[#8B8B8B]">Energy Class</span>
            <p className="font-semibold text-[#3D405B]">
              {listing.energy_class || listing.hwb_value ? `${listing.energy_class || 'HWB: ' + listing.hwb_value}` : 'N/A'}
            </p>
          </div>
        </div>

        {breakdownEntries.length > 0 && (
          <div className="mb-6">
            <h2 className="text-lg font-semibold mb-3 text-[#3D405B]">Score Breakdown</h2>
            <div className="space-y-2">
              {breakdownEntries.map(([key, data]: [string, any]) => (
                <div key={key} className="flex justify-between items-center p-2 bg-[#F9F7F4] rounded">
                  <span className="text-[#2D2D2D] capitalize">{key.replace(/_/g, ' ')}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-24 h-2 bg-[#E8E4E0] rounded-full overflow-hidden">
                      <div
                        className="h-full bg-green-500"
                        style={{ width: `${typeof data === 'object' ? (data.normalized_score || 0) : 0}%` }}
                      />
                    </div>
                    <span className="text-sm font-medium text-[#3D405B]">
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
            className="bg-[#E8E4E0] hover:bg-[#D0CCC8] text-[#3D405B] px-4 py-2 rounded transition-colors"
          >
            Back to Dashboard
          </Link>
        </div>
      </div>
    </div>
  )
}