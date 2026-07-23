import './Skeleton.css'

function Skeleton({ width = '100%', height = '14px', radius = '4px', className = '', style }) {
  return (
    <div
      className={`ui-skeleton ${className}`}
      style={{ width, height, borderRadius: radius, ...style }}
    />
  )
}

export default Skeleton
