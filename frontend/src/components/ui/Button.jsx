import './Button.css'

function Button({ variant = 'primary', size = 'md', className = '', ...props }) {
  const classes = ['ui-btn', `ui-btn-${variant}`, `ui-btn-${size}`, className]
    .filter(Boolean)
    .join(' ')

  return <button className={classes} {...props} />
}

export default Button
