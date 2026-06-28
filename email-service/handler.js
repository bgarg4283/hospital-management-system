const nodemailer = require('nodemailer')

const transporter = nodemailer.createTransport({
  host: 'smtp.gmail.com',
  port: 587,
  secure: false,
  auth: {
    user: 'iitian.bhaveshgarg@gmail.com',      // ← change this
    pass: 'vylz taul nuzv jwnm',  // ← change this
  }
})

module.exports.send_email = async (event) => {
  try {
    const body = typeof event.body === 'string' ? JSON.parse(event.body) : event.body
    const { trigger, payload } = body
    const { email, name } = payload

    let subject, text

    if (trigger === 'SIGNUP_WELCOME') {
      subject = `Welcome to HMS, ${name}!`
      text = `Hi ${name},\n\nWelcome to HMS! Your account is ready.\n\nLogin at: http://localhost:8000\n\nRegards,\nHMS Team`

    } else if (trigger === 'BOOKING_CONFIRMATION') {
      const { doctor_name, date, start_time, end_time } = payload
      subject = `Appointment Confirmed — ${date} at ${start_time}`
      text = `Hi ${name},\n\nYour appointment is confirmed!\n\nDoctor : Dr. ${doctor_name}\nDate   : ${date}\nTime   : ${start_time} - ${end_time}\n\nPlease arrive 10 minutes early.\n\nRegards,\nHMS Team`

    } else {
      return { statusCode: 400, body: JSON.stringify({ error: 'Unknown trigger' }) }
    }

    await transporter.sendMail({
      from: 'your_gmail@gmail.com',   // ← change this
      to: email,
      subject,
      text
    })

    return {
      statusCode: 200,
      body: JSON.stringify({ status: 'sent', to: email })
    }

  } catch (err) {
    console.error('Email error:', err)
    return {
      statusCode: 200,
      body: JSON.stringify({ status: 'logged', error: err.message })
    }
  }
}