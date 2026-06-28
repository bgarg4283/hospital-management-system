const http = require('http')
const nodemailer = require('nodemailer')

const SMTP_USER = ''      // ← change
const SMTP_PASSWORD = ''      // ← change

const transporter = nodemailer.createTransport({
  host: 'smtp.gmail.com',
  port: 587,
  secure: false,
  auth: { user: SMTP_USER, pass: SMTP_PASSWORD }
})

const server = http.createServer(async (req, res) => {
  if (req.method === 'POST' && (req.url === '/email' || req.url === '/dev/email')) {
    let body = ''
    req.on('data', chunk => body += chunk)
    req.on('end', async () => {
      try {
        const { trigger, payload } = JSON.parse(body)
        const { email, name } = payload
        let subject, text

        if (trigger === 'SIGNUP_WELCOME') {
          subject = `Welcome to HMS, ${name}!`
          text = `Hi ${name},\n\nWelcome to HMS! Your account is ready.\n\nLogin: http://localhost:8000\n\nRegards,\nHMS Team`

        } else if (trigger === 'BOOKING_CONFIRMATION') {
          const { doctor_name, date, start_time, end_time } = payload
          subject = `Appointment Confirmed — ${date} at ${start_time}`
          text = `Hi ${name},\n\nAppointment confirmed!\n\nDoctor: Dr. ${doctor_name}\nDate: ${date}\nTime: ${start_time}–${end_time}\n\nPlease arrive 10 minutes early.\n\nRegards,\nHMS Team`

        } else {
          res.writeHead(400)
          res.end(JSON.stringify({ error: 'Unknown trigger' }))
          return
        }

        await transporter.sendMail({ from: SMTP_USER, to: email, subject, text })
        console.log(`✅ Email sent to ${email} | trigger: ${trigger}`)
        res.writeHead(200, { 'Content-Type': 'application/json' })
        res.end(JSON.stringify({ status: 'sent', to: email }))

      } catch (err) {
        console.error('❌ Error:', err.message)
        res.writeHead(200, { 'Content-Type': 'application/json' })
        res.end(JSON.stringify({ status: 'logged', error: err.message }))
      }
    })
  } else {
    res.writeHead(404)
    res.end(JSON.stringify({ error: 'Not found' }))
  }
})

server.listen(3000, () => {
  console.log('📧 Email service running at http://localhost:3000')
  console.log('POST http://localhost:3000/email')
})