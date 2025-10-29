local function fail(s, ...) ya.notify { title = "Zoxide", content = s:format(...), timeout = 5, level = "error" } end

local function prompt()
    return ya.input {
    title = "Zoxide - Jump to Folder",
    position = { "center", w = 50 },
        realtime = false
    }
end

local function split_args(str)
    local t = {}
    for arg in string.gmatch(str, "%S+") do
        table.insert(t, arg)
    end
    return t
end

local function entry()
    local input, event = prompt()
    if event == 2 then
        return
    end
    if not input or input == "" then
        return
    end

    local args = { "query" }
    for _, a in ipairs(split_args(input)) do
        table.insert(args, a)
    end

    local child, err1 = Command("zoxide")
        :arg(args)
        :env("SHELL", "sh")
        :env("CLICOLOR", 1)
        :env("CLICOLOR_FORCE", 1)
        :stdout(Command.PIPED)
        :stderr(Command.PIPED)
        :spawn()
    if not child then
        return fail("Failed to start `zoxide`, error: " .. err1)
    end

    local output, err2 = child:wait_with_output()
    if not output then
        return fail("Cannot read `zoxide` output, error: " .. err2)
    elseif not output.status.success then
        return fail("`zoxide` exited with code %s: %s", output.status.code, output.stderr:gsub("^zoxide:%s*", ""))
    end

    local target = output.stdout:gsub("\n$", "")
    if target ~= "" then
        ya.emit("cd", {target, raw=true})
    end
end

return { entry = entry }
